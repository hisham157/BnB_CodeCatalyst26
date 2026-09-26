import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text

from app.database import initialize_database
from app.models import Interview, InterviewTurn
from app.report_schemas import (ClaimInterpretation, ExtractedClaims, ReportNarrative, ResumeClaim,
                                SkillEvidence)
from app.services.gemini_service import AIServiceError
from app.services.rag_service import RagService
from app.services.report_service import (ReportService, aggregate_skills, get_report_service,
                                         retrieve_claim_turns)
from tests.test_interviews import client, create
from tests.test_rag import KeywordEmbeddings


class ReportAI:
    def __init__(self):
        self.calls = 0
        self.fail = False
        self.bad_skill = False
        self.bad_reference = False
        self.contexts = []

    def ensure_configured(self):
        pass

    def generate(self, schema, task, context):
        self.calls += 1
        self.contexts.append(context)
        if self.fail:
            raise AIServiceError("Synthetic test failure")
        if schema is ExtractedClaims:
            assert "job-relevant professional claims" in task
            assert "protected" in task
            assert context["role"] and context["allowed_skills"]
            return ExtractedClaims(claims=[ResumeClaim(claim_text="Python project delivery", claim_type="PROJECT", related_skill="Python")])
        assert schema is ReportNarrative
        statement = {"text": "Candidate described Python project delivery.", "supporting_turns": [99 if self.bad_reference else 1]}
        notes = [{"skill": item["skill"], "why": "Candidate described their approach.", "supporting_turns": item["supporting_turns"], "remaining_gap": "More examples are needed."} for item in context["skill_aggregates"] if item["evidence_level"]]
        if self.bad_skill:
            notes.append({"skill": "Unassessed leadership", "why": "Invented", "supporting_turns": [1], "remaining_gap": "None"})
        return ReportNarrative(summary=[statement], skill_notes=notes,
            claim_notes=[dict(claim_index=claim["claim_index"], status="SUPPORTED_BY_EXPLANATION" if claim["retrieved_turns"] else "NOT_ASSESSED", evidence="Project discussed." if claim["retrieved_turns"] else "Not assessed.", supporting_turns=claim["retrieved_turns"], remaining_gap="Outcome not independently verified.") for claim in context["claims"]],
            adaptation={"challenge_turn": context["adaptation_pairs"][0][1], "interpretation": "Candidate revised their approach."} if context["adaptation_pairs"] else None,
            practice_improvement={"challenge_turn": context["teaching_pairs"][0][1], "interpretation": "Candidate applied the discussed concept."} if context["teaching_pairs"] else None,
            strengths=[statement], gaps=[statement], next_steps=[statement])


def completed(client, mode="recruiter", special=None):
    interview_id = create(client, mode=mode).json()["id"]
    with client.test_sessions() as db:
        interview = db.get(Interview, interview_id)
        interview.status = "completed"
        interview.resume_text = "Python project delivery. Personal details excluded."
        rubric = json.dumps(dict(relevance_score=4, specificity_score=4, depth_score=4, evidence_score=4))
        first = InterviewTurn(interview_id=interview_id, turn_number=1, question="Describe your Python project.", answer_text="Python project delivery with tests.", skill="Python", difficulty=2, evaluation_json=rubric)
        db.add(first)
        db.flush()
        if special:
            db.add(InterviewTurn(interview_id=interview_id, turn_number=2, question="What would change?", answer_text="Python alternative approach.", skill="Python", difficulty=2, evaluation_json=rubric, turn_type=special, parent_turn_id=first.id, changed_condition="Budget is fixed." if special == "CHANGE_CONSTRAINT" else None, teaching_note="Consider the trade-off." if special == "TEACH_NEW_CHALLENGE" else None))
        db.commit()
    ai = ReportAI()
    client.app.dependency_overrides[get_report_service] = lambda: ReportService(ai, RagService(KeywordEmbeddings()))
    return interview_id, ai


@pytest.mark.parametrize("level,label", [(0, "NOT_ASSESSED"), (1, "LIMITED_EVIDENCE"), (2, "LIMITED_EVIDENCE"), (3, "MODERATE"), (4, "STRONG"), (5, "STRONG")])
def test_evidence_levels(level, label):
    item = SkillEvidence(skill="Example", evidence_level=level, label=label, why="Evidence", remaining_gap="Gap", supporting_turns=[1] if level else [])
    assert item.label == label
    with pytest.raises(ValidationError):
        SkillEvidence(**(item.model_dump() | {"label": "STRONG" if level < 4 else "NOT_ASSESSED"}))


@pytest.mark.parametrize("status", ["SUPPORTED_BY_EXPLANATION", "NEEDS_CLARIFICATION", "NOT_ASSESSED"])
def test_claim_statuses(status):
    assert ClaimInterpretation(claim_index=0, status=status, evidence="Evidence", supporting_turns=[], remaining_gap="Gap").status == status


def test_retrieval_matches_answers_without_creating_scores():
    claim = ResumeClaim(claim_text="Python project", claim_type="PROJECT", related_skill="Python")
    turns = [SimpleNamespace(turn_number=1, answer_text="Marketing channels"), SimpleNamespace(turn_number=2, answer_text="Python project testing")]
    assert retrieve_claim_turns([claim], turns, RagService(KeywordEmbeddings())) == [[2]]


@pytest.mark.parametrize("mode", ["recruiter", "practice"])
def test_report_persisted_cached_and_integrity_separate(client, mode):
    interview_id, ai = completed(client, mode)
    base = f"/api/interviews/{interview_id}"
    assert client.get(base + "/report").status_code == 404
    result = client.post(base + "/finalize")
    assert result.status_code == 200, result.text
    report = result.json()["report"]
    assert report["mode"] == mode
    skills = {item["skill"]: item for item in report["skill_evidence"]}
    assert skills["Python"]["label"] == "STRONG"
    assert skills["SQL"]["label"] == "NOT_ASSESSED"
    assert report["adaptation_evidence"] is None
    assert ("practice_recommendations" in report) == (mode == "practice")
    assert ("resume_claims" in report) == (mode == "recruiter")
    calls = ai.calls
    event = client.post(base + "/integrity-events", json={"event_type": "FACE_MISSING", "started_at_seconds": 1, "ended_at_seconds": 4, "turn_number": 1}).json()
    client.patch(base + f"/integrity-events/{event['id']}/explanation", json={"explanation": "Adjusted camera."})
    assert client.get(base + "/integrity-events").json()[0]["candidate_explanation"] == "Adjusted camera."
    assert client.get(base + "/report").json() == result.json()
    assert client.post(base + "/finalize").json() == result.json()
    assert ai.calls == calls
    assert all("integrity" not in json.dumps(context).lower() for context in ai.contexts)
    with client.test_sessions() as db:
        assert db.get(Interview, interview_id).final_report_json
        assert aggregate_skills(db.get(Interview, interview_id))[0].evidence_level == 4


@pytest.mark.parametrize("bad_field", ["bad_skill", "bad_reference"])
def test_fabricated_evidence_rejected(client, bad_field):
    interview_id, ai = completed(client)
    setattr(ai, bad_field, True)
    assert client.post(f"/api/interviews/{interview_id}/finalize").status_code == 502
    with client.test_sessions() as db:
        assert db.get(Interview, interview_id).final_report_json is None


def test_generation_failure_preserves_transcript_and_retry(client):
    interview_id, ai = completed(client)
    ai.fail = True
    base = f"/api/interviews/{interview_id}"
    assert client.post(base + "/finalize").status_code == 503
    assert client.get(base + "/session").json()["turns"][0]["answer_text"]
    assert client.get(base + "/integrity-events").status_code == 200
    ai.fail = False
    assert client.post(base + "/finalize").status_code == 200


@pytest.mark.parametrize("mode,kind,key", [("recruiter", "CHANGE_CONSTRAINT", "adaptation_evidence"), ("practice", "TEACH_NEW_CHALLENGE", "practice_improvement")])
def test_report_links_original_and_revised_answers(client, mode, kind, key):
    interview_id, _ = completed(client, mode, kind)
    response = client.post(f"/api/interviews/{interview_id}/finalize")
    assert response.status_code == 200, response.text
    pair = response.json()["report"][key]
    assert pair["original_turn"] == 1 and pair["challenge_turn"] == 2
    assert "Python alternative" in pair.get("revised_approach", pair.get("second_attempt", ""))


def test_incomplete_unknown_and_busy_reports(client):
    from app.routers.interview_session import _locks
    interview_id = create(client).json()["id"]
    assert client.post(f"/api/interviews/{interview_id}/finalize").status_code == 409
    assert client.get("/api/interviews/9999/report").status_code == 404
    interview_id, ai = completed(client)
    with _locks[interview_id % len(_locks)]:
        response = client.post(f"/api/interviews/{interview_id}/finalize")
        assert response.status_code == 202
        assert ai.calls == 0
    assert client.get("/api/interviews").status_code == 200


def test_phase4_upgrade_keeps_existing_turns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE interview_turns (id INTEGER PRIMARY KEY, question TEXT)"))
        db.execute(text("INSERT INTO interview_turns VALUES (1, 'Existing question')"))
    initialize_database(engine)
    initialize_database(engine)
    with engine.connect() as db:
        row = db.execute(text("SELECT question, turn_type, parent_turn_id FROM interview_turns")).one()
        assert tuple(row) == ("Existing question", "NORMAL", None)
    assert {"final_report_json", "report_generated_at"} <= {c["name"] for c in inspect(engine).get_columns("interviews")}
    engine.dispose()


def test_claim_must_be_grounded_in_resume(client):
    interview_id, ai = completed(client)
    with client.test_sessions() as db:
        interview = db.get(Interview, interview_id)
        interview.resume_text = "No such project in this resume."
        db.commit()
    assert client.post(f"/api/interviews/{interview_id}/finalize").status_code == 502


@pytest.mark.parametrize("evaluation", ['{}', 'null', 'bad json'])
def test_legacy_practice_transcript_survives_missing_feedback(client, evaluation):
    interview_id, _ = completed(client, "practice")
    with client.test_sessions() as db:
        interview = db.get(Interview, interview_id)
        interview.turns[0].evaluation_json = evaluation
        interview.interview_plan_json = "bad json"
        db.commit()
    response = client.get(f"/api/interviews/{interview_id}/session")
    assert response.status_code == 200
    assert response.json()["turns"][0]["answer_text"]
    assert response.json()["turns"][0]["practice_feedback"] is None
