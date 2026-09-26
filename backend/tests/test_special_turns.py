from types import SimpleNamespace

import pytest

from app.schemas import InterviewPlan, TurnDecision
from app.services.interview_engine import InterviewEngine, get_interview_engine
from tests.test_interview_engine import FakeAI, FakeRag, new_interview
from tests.test_interviews import client


def decision(action="CHANGE_CONSTRAINT", **changes):
    fields = dict(relevance_score=4, specificity_score=4, depth_score=4, evidence_score=4,
        decision=action, decision_reason="Test the approach", next_skill="Analysis", next_difficulty=2,
        next_question="How would you adjust with a fixed budget?", practice_feedback="Explain a trade-off.",
        changed_condition="Budget cannot increase.", testable_approach=True)
    if action == "TEACH_AND_RETRY":
        fields.update(changed_condition=None, depth_score=1, conceptual_gap="Confuses revenue and profit.", teaching_note="Profit subtracts costs from revenue.")
    return TurnDecision(**(fields | changes))


def test_special_action_limits_and_mode_boundaries():
    engine = InterviewEngine(FakeAI(), FakeRag())
    plan = InterviewPlan(role="Analyst", interview_focus=[{"skill": "Analysis", "priority": 5}], candidate_context_summary="Example", recommended_starting_difficulty=2)
    turns = [SimpleNamespace(question="Original question?", skill="Analysis", difficulty=2, turn_type="NORMAL")]
    assert not engine.decision_issues(decision(), turns, plan)
    assert engine.decision_issues(decision(testable_approach=False), turns, plan)
    assert engine.decision_issues(decision(depth_score=1), turns, plan)
    assert engine.decision_issues(decision("TEACH_AND_RETRY"), turns, plan, "recruiter")
    assert not engine.decision_issues(decision("TEACH_AND_RETRY"), turns, plan, "practice")
    assert engine.decision_issues(decision("TEACH_AND_RETRY", conceptual_gap=None), turns, plan, "practice")
    assert engine.decision_issues(decision("TEACH_AND_RETRY", next_question="Original question?"), turns, plan, "practice")
    turns[0].turn_type = "CHANGE_CONSTRAINT"
    assert engine.decision_issues(decision(), turns, plan)
    turns[0].turn_type = "TEACH_NEW_CHALLENGE"
    assert engine.decision_issues(decision("TEACH_AND_RETRY"), turns, plan, "practice")


class SpecialAI(FakeAI):
    def __init__(self, action):
        super().__init__()
        self.action = action

    def generate(self, schema, task, context):
        if schema is TurnDecision and len(context["previous_questions"]) == 1:
            return decision(self.action)
        return super().generate(schema, task, context)


@pytest.mark.parametrize("mode,action,kind", [("recruiter", "CHANGE_CONSTRAINT", "CHANGE_CONSTRAINT"), ("practice", "TEACH_AND_RETRY", "TEACH_NEW_CHALLENGE")])
def test_full_session_persists_one_special_turn(client, mode, action, kind):
    client.app.dependency_overrides[get_interview_engine] = lambda: InterviewEngine(SpecialAI(action), FakeRag())
    base = f"/api/interviews/{new_interview(client, mode)}"
    assert client.post(base + "/start").status_code == 200
    for number in range(1, 7):
        result = client.post(base + "/answer", json={"answer_text": "I compared alternatives and measured project outcomes.", "turn_number": number})
        assert result.status_code == 200, result.text
    turns = result.json()["turns"]
    assert sum(turn["turn_type"] == kind for turn in turns) == 1
    assert turns[1]["parent_turn_id"] == turns[0]["id"]
    assert turns[1]["question"] != turns[0]["question"]
    assert bool(turns[1]["teaching_note"]) == (mode == "practice")
    assert result.json()["completed"]
