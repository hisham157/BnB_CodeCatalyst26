import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.database import initialize_database
from app.models import Interview
from app.schemas import FirstQuestion, InterviewPlan, TurnDecision
from app.services.gemini_service import AIServiceError, GeminiService, generation_schema
from app.services.interview_engine import InterviewEngine, get_interview_engine
from tests.test_interviews import client, create, docx_bytes


class FakeRag:
    def retrieve(self, interview, query):
        return [{"source": "RESUME", "text": "Candidate improved financial reporting and communication."}]


class FakeAI:
    def __init__(self):
        self.contexts = []
        self.fail = False
        self.repeat = False

    def ensure_configured(self):
        pass

    def generate(self, schema, task, context):
        self.contexts.append(context)
        if self.fail:
            raise AIServiceError("AI interview service is temporarily unavailable.")
        if schema is InterviewPlan:
            return InterviewPlan(
                role=context["role"],
                interview_focus=[{"skill": "Analysis", "priority": 5}, {"skill": "Communication", "priority": 4}],
                candidate_context_summary="Experience in professional analysis.", recommended_starting_difficulty=2,
            )
        if schema is FirstQuestion:
            return FirstQuestion(question="How did you improve financial reporting?", skill="Analysis", difficulty=2)
        number = len(context["previous_questions"])
        next_skill = "Communication" if (number // 2) % 2 else "Analysis"
        switch = next_skill != context["current_skill"]
        return TurnDecision(
            relevance_score=4, specificity_score=4, depth_score=4, evidence_score=3,
            decision="SWITCH_TOPIC" if switch else "PROBE_DEEPER",
            decision_reason="Explore another example of the candidate's reasoning.",
            next_skill=next_skill, next_difficulty=2,
            next_question=context["previous_questions"][0] if self.repeat else f"How would you handle professional scenario {number + 1}?",
            practice_feedback="Explain the outcome using a concrete example.",
        )


@pytest.fixture
def ai_client(client):
    ai = FakeAI()
    engine = InterviewEngine(ai, FakeRag())
    client.app.dependency_overrides[get_interview_engine] = lambda: engine
    return client, ai


def new_interview(client, mode="recruiter"):
    result = create(client, mode=mode)
    assert result.status_code == 201
    return result.json()["id"]


def test_practice_only_requires_role_and_resume(client):
    response = client.post("/api/interviews", data={"mode": "practice", "job_title": "Financial Analyst"}, files={"resume": ("resume.docx", docx_bytes())})
    assert response.status_code == 201
    assert response.json()["mode"] == "practice"
    assert response.json()["required_skills"] == []


def test_invalid_mode(client):
    assert create(client, mode="other").status_code == 422


@pytest.mark.parametrize("mode", ["recruiter", "practice"])
def test_shared_engine_full_session(ai_client, mode):
    client, ai = ai_client
    interview_id = new_interview(client, mode)
    base = f"/api/interviews/{interview_id}"
    first = client.post(base + "/start")
    assert first.status_code == 200
    assert first.json()["turn_number"] == 1
    assert first.json()["status"] == "in_progress"
    assert client.post(base + "/start").json() == first.json()
    assert len(ai.contexts) == 2  # A repeated start does not call AI again.
    for number in range(1, 7):
        response = client.post(base + "/answer", json={"answer_text": f"Example answer {number}", "turn_number": number})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["turns"][number - 1]["answer_text"] == f"Example answer {number}"
        assert all(1 <= turn["difficulty"] <= 5 for turn in result["turns"])
        assert ("practice_feedback" in result["turns"][0]) == (mode == "practice")
        assert "evaluation_json" not in result["turns"][0]
        assert "resume_text" not in result
        if number < 6:
            assert result["turn_number"] == number + 1
        else:
            assert result["completed"] is True
            assert result["current_turn"] is None
            assert len(result["turns"]) == 6
    assert ai.contexts[-1]["previous_turn_summaries"][0]["answer_excerpt"] == "Example answer 1"
    assert client.get(base + "/session").json() == result
    assert client.post(base + "/start").json()["completed"]
    assert client.post(base + "/answer", json={"answer_text": "seventh"}).status_code == 409
    with client.test_sessions() as db:
        stored = db.get(Interview, interview_id)
        assert stored.interview_plan_json
        assert stored.turns[0].evaluation_json


def test_failures_do_not_partially_save_and_retries_are_safe(ai_client):
    client, ai = ai_client
    base = f"/api/interviews/{new_interview(client)}"
    client.post(base + "/start")
    ai.fail = True
    assert client.post(base + "/answer", json={"answer_text": "answer"}).status_code == 503
    data = client.get(base + "/session").json()
    assert data["turns"][0]["answer_text"] is None
    ai.fail = False
    ai.repeat = True
    assert client.post(base + "/answer", json={"answer_text": "answer"}).status_code == 502
    assert client.get(base + "/session").json()["turns"][0]["answer_text"] is None
    ai.repeat = False
    assert client.post(base + "/answer", json={"answer_text": "answer", "turn_number": 1}).status_code == 200
    assert client.post(base + "/answer", json={"answer_text": "duplicate", "turn_number": 1}).status_code == 409
    assert client.post(base + "/answer", json={"answer_text": "   "}).status_code == 422


def test_missing_key_is_controlled(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    base = f"/api/interviews/{new_interview(client)}"
    response = client.post(base + "/start")
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]
    assert client.get(base + "/session").json()["status"] == "created"


def test_schema_difficulty_bounds():
    for difficulty in (0, 6):
        with pytest.raises(ValidationError):
            FirstQuestion(question="Example?", skill="Analysis", difficulty=difficulty)


def test_skill_streak_guardrail():
    engine = InterviewEngine(FakeAI(), FakeRag())
    plan = InterviewPlan(role="Analyst", interview_focus=[{"skill": "Analysis", "priority": 5}, {"skill": "Communication", "priority": 4}], candidate_context_summary="Experience", recommended_starting_difficulty=2)
    turns = [SimpleNamespace(question=f"Question {number}", skill="Analysis", difficulty=2) for number in range(3)]
    decision = TurnDecision(relevance_score=3, specificity_score=3, depth_score=3, evidence_score=3, decision="CLARIFY", decision_reason="Unclear", next_skill="Analysis", next_difficulty=2, next_question="Clarify your role?", practice_feedback="Give an example.")
    assert not engine.decision_issues(decision, turns[:2], plan)
    assert engine.decision_issues(decision, turns, plan)


def test_phase1_database_upgrade_preserves_rows(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE interviews (id INTEGER PRIMARY KEY, job_title VARCHAR NOT NULL, job_description TEXT NOT NULL, required_skills TEXT NOT NULL, resume_filename VARCHAR NOT NULL, resume_text TEXT NOT NULL, status VARCHAR, created_at DATETIME)"))
        db.execute(text("INSERT INTO interviews VALUES (1, 'Analyst', 'Analyze reports', '[\"Analysis\"]', 'resume.docx', 'Existing resume content', 'created', '2026-09-26')"))
    initialize_database(engine)
    initialize_database(engine)
    with engine.connect() as db:
        row = db.execute(text("SELECT job_title, resume_text, mode, interview_plan_json FROM interviews WHERE id=1")).one()
        assert tuple(row) == ("Analyst", "Existing resume content", "recruiter", None)
    assert "interview_turns" in inspect(engine).get_table_names()
    engine.dispose()


@pytest.mark.parametrize("failure,expected", [("malformed", 502), ("rate", 429), ("network", 503)])
def test_gemini_failures_without_network(monkeypatch, failure, expected):
    from google import genai
    from google.genai import errors

    class Client:
        def __init__(self, **kwargs):
            self.models = self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def generate_content(self, **kwargs):
            assert kwargs["config"].response_json_schema == generation_schema(FirstQuestion)
            assert kwargs["config"].response_schema is None
            if failure == "rate":
                raise errors.ClientError(429, {"error": {"message": "Quota exceeded"}})
            if failure == "network":
                raise ConnectionError("network error")
            return SimpleNamespace(parsed=None, text="invalid json")

    monkeypatch.setenv("GEMINI_API_KEY", "test-only-fake-key")
    monkeypatch.setattr(genai, "Client", Client)
    with pytest.raises(AIServiceError) as error:
        GeminiService().generate(FirstQuestion, "Question", {})
    assert error.value.status_code == expected

def test_overlapping_start_recovers_without_duplicate_generation(ai_client):
    from app.routers.interview_session import _locks
    client, ai = ai_client
    interview_id = new_interview(client)
    base = f"/api/interviews/{interview_id}"
    lock = _locks[interview_id % len(_locks)]
    with lock:
        response = client.post(base + "/start")
        assert response.status_code == 202
        assert response.json() == {"status": "starting"}
        assert response.headers["Retry-After"] == "2"
        assert not ai.contexts
    first = client.post(base + "/start")
    assert first.status_code == 200
    count = len(ai.contexts)
    repeated = client.post(base + "/start")
    assert repeated.json() == first.json()
    assert len(ai.contexts) == count
