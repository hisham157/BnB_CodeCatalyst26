import json

from fastapi import HTTPException

from ..models import InterviewTurn
from ..schemas import FirstQuestion, InterviewPlan, TurnDecision
from .gemini_service import AIServiceError, GeminiService
from .rag_service import RagService

MAX_QUESTIONS = 6


def normalized(text):
    return " ".join(text.casefold().split()).rstrip("?.! ")


class InterviewEngine:
    def __init__(self, ai=None, rag=None):
        self.ai = ai or GeminiService()
        self.rag = rag or RagService()

    def context(self, interview, query):
        return {
            "role": interview.job_title,
            "mode": interview.mode,
            "selected_skills": json.loads(interview.required_skills),
            "retrieved_chunks": self.rag.retrieve(interview, query),
        }

    def start(self, db, interview):
        if interview.status == "completed" or interview.turns:
            return
        self.ai.ensure_configured()
        context = self.context(interview, f"{interview.job_title} professional experience {interview.required_skills}")
        plan = (
            InterviewPlan.model_validate_json(interview.interview_plan_json)
            if interview.interview_plan_json else self.ai.generate(
                InterviewPlan,
                "Create a short interview plan from the retrieved professional evidence. "
                "Prioritize selected skills. If none are provided, infer role-relevant focus areas. "
                "Do not invent company requirements. Include multiple focus areas where appropriate.",
                context,
            )
        )
        context["plan"] = plan.model_dump()
        context["required_skill"] = plan.interview_focus[0].skill
        context["required_difficulty"] = plan.recommended_starting_difficulty
        question = self.ai.generate(
            FirstQuestion,
            "Generate the first personalized question. Use required_skill and required_difficulty exactly. "
            "Reference a relevant actual experience when available; otherwise ask a role-relevant scenario.",
            context,
        )
        if normalized(question.skill) != normalized(context["required_skill"]) or question.difficulty != context["required_difficulty"]:
            raise AIServiceError("AI returned a question inconsistent with the plan. Please retry.", 502)
        interview.interview_plan_json = plan.model_dump_json()
        interview.status = "in_progress"
        db.add(InterviewTurn(
            interview_id=interview.id, turn_number=1, question=question.question,
            skill=question.skill, difficulty=question.difficulty,
        ))

    def decision_issues(self, decision, turns, plan, mode="recruiter"):
        current = turns[-1]
        issues = []
        allowed = {normalized(item.skill) for item in plan.interview_focus}
        if normalized(decision.next_skill) not in allowed:
            issues.append("Choose next_skill from the interview plan.")
        if normalized(decision.next_question) in {normalized(turn.question) for turn in turns}:
            issues.append("Ask a new question; never repeat a previous question.")
        streak = 0
        for turn in reversed(turns):
            if normalized(turn.skill) != normalized(current.skill):
                break
            streak += 1
        same_skill = normalized(decision.next_skill) == normalized(current.skill)
        special = decision.decision in {"CHANGE_CONSTRAINT", "TEACH_AND_RETRY"}
        if len(allowed) > 1 and same_skill and (streak >= 3 or (streak >= 2 and decision.decision != "CLARIFY" and not special)):
            issues.append("Switch to another important skill now; at most one clarification after two consecutive questions is allowed.")
        if decision.decision == "SWITCH_TOPIC" and same_skill and len(allowed) > 1:
            issues.append("SWITCH_TOPIC must select another skill.")
        if decision.decision != "SWITCH_TOPIC" and not same_skill:
            issues.append("A change in skill must use SWITCH_TOPIC.")
        if decision.decision == "INCREASE_DIFFICULTY" and decision.next_difficulty != min(5, current.difficulty + 1):
            issues.append(f"Increasing difficulty requires level {min(5, current.difficulty + 1)}.")
        if decision.decision == "DECREASE_DIFFICULTY" and decision.next_difficulty != max(1, current.difficulty - 1):
            issues.append(f"Decreasing difficulty requires level {max(1, current.difficulty - 1)}.")
        types = {getattr(turn, "turn_type", "NORMAL") for turn in turns}
        if decision.decision == "CHANGE_CONSTRAINT":
            if "CHANGE_CONSTRAINT" in types:
                issues.append("The changed-condition challenge was already used. Choose a normal action.")
            if not decision.changed_condition or not decision.testable_approach or min(decision.specificity_score, decision.depth_score) < 3:
                issues.append("CHANGE_CONSTRAINT requires a substantive testable approach, specificity/depth >=3, and exactly one changed condition.")
        elif decision.changed_condition:
            issues.append("Only CHANGE_CONSTRAINT may supply changed_condition.")
        if decision.decision == "TEACH_AND_RETRY":
            if mode != "practice" or "TEACH_NEW_CHALLENGE" in types:
                issues.append("Teaching is practice-only, at most once. Choose a normal action.")
            if not decision.teaching_note or not decision.conceptual_gap or decision.depth_score > 2:
                issues.append("Teaching requires a specific conceptual gap, low depth and a brief teaching note, not merely a short answer.")
        elif decision.teaching_note:
            issues.append("Only TEACH_AND_RETRY may supply teaching_note.")
        return issues

    def answer(self, db, interview, answer):
        turns = list(interview.turns)
        if interview.status != "in_progress" or not turns or turns[-1].answer_text is not None:
            raise HTTPException(409, "There is no unanswered question. Start or reload the interview.")
        current = turns[-1]
        if answer.turn_number is not None and answer.turn_number != current.turn_number:
            raise HTTPException(409, "This question was already answered. Reload the interview to continue.")
        self.ai.ensure_configured()
        plan = InterviewPlan.model_validate_json(interview.interview_plan_json)
        context = self.context(interview, f"{current.skill} {current.question} {answer.answer_text[:2000]}")
        context.update({
            "plan": plan.model_dump(),
            "current_question": current.question,
            "current_skill": current.skill,
            "current_difficulty": current.difficulty,
            "answer": answer.answer_text,
            "previous_turn_summaries": [{
                "question": turn.question, "answer_excerpt": (turn.answer_text or "")[:1500],
                "skill": turn.skill, "difficulty": turn.difficulty,
                "decision": turn.decision, "reason": turn.decision_reason,
            } for turn in turns[:-1]],
            "previous_questions": [turn.question for turn in turns],
            "final_answer": current.turn_number >= MAX_QUESTIONS,
            "used_special_turns": [turn.turn_type for turn in turns if turn.turn_type != "NORMAL"],
        })
        task = (
            "Evaluate this answer using the rubric and prior answers, then choose an adaptive action and next question. "
            "For unclear answers clarify or simplify; for strong depth probe or increase difficulty; "
            "for repeated struggles simplify or switch. Do not decide using one score threshold. "
            "After two consecutive questions on a skill switch to another plan skill, unless one clarification is needed. "
            "After three, switch if another plan skill exists. Never repeat a question. "
            "INCREASE/DECREASE changes difficulty by one within 1-5. A skill change uses SWITCH_TOPIC. "
            "When a substantive answer presents a testable solution, consider CHANGE_CONSTRAINT once per interview: "
            "change exactly one important assumption, set testable_approach=true and changed_condition, and ask how the approach changes. "
            "Keep the same skill. Do not force it for vague answers. Prefer an eligible opportunity early enough to answer it. "
            "Only in practice mode, once, TEACH_AND_RETRY may address a specific conceptual_gap with depth <=2: "
            "supply teaching_note of at most two short sentences and a DIFFERENT application question on the same concept/skill. "
            "Never coach recruiter interviews. Do not teach merely because wording is brief. "
            "Either special action may extend a two-question skill streak by one, but after three switch. "
            "Unused optional fields must be null. Do not select a special action on final_answer. "
            "If final_answer is true, still evaluate and supply schema fields, but no further question will be asked."
        )
        for attempt in range(2):
            decision = self.ai.generate(TurnDecision, task, context)
            if context["final_answer"]:
                issues = ["No special action or coaching on the final answer."] if decision.decision in {"CHANGE_CONSTRAINT", "TEACH_AND_RETRY"} or decision.changed_condition or decision.teaching_note else []
            else:
                issues = self.decision_issues(decision, turns, plan, interview.mode)
            if not issues:
                break
            context["required_corrections"] = issues
        else:
            raise AIServiceError("AI could not produce a valid next question. Your answer has not been saved; please retry.", 502)

        # Commit answer, evaluation and next question together; AI failures leave a retryable turn.
        current.answer_text = answer.answer_text
        current.evaluation_json = decision.model_dump_json()
        current.decision = decision.decision
        current.decision_reason = decision.decision_reason
        if current.turn_number >= MAX_QUESTIONS:
            interview.status = "completed"
        else:
            db.add(InterviewTurn(
                interview_id=interview.id, turn_number=current.turn_number + 1,
                question=decision.next_question, skill=decision.next_skill,
                difficulty=max(1, min(5, decision.next_difficulty)),
                turn_type={"CHANGE_CONSTRAINT": "CHANGE_CONSTRAINT", "TEACH_AND_RETRY": "TEACH_NEW_CHALLENGE"}.get(decision.decision, "NORMAL"),
                changed_condition=decision.changed_condition,
                teaching_note=decision.teaching_note if interview.mode == "practice" else None,
                parent_turn_id=current.id if decision.decision in {"CHANGE_CONSTRAINT", "TEACH_AND_RETRY"} else None,
            ))


engine = InterviewEngine()


def get_interview_engine():
    return engine
