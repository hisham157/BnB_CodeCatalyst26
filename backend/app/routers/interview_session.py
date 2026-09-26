import json
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Interview
from ..schemas import AnswerInput, InterviewPlan
from ..services.gemini_service import AIServiceError
from ..services.interview_engine import MAX_QUESTIONS, get_interview_engine
from .interviews import metadata

router = APIRouter(prefix="/api/interviews", tags=["interview session"])
# Fixed-size locks serialize mutations in this single-process prototype without a growing lock cache.
_locks = [Lock() for _ in range(32)]


def load_interview(db, interview_id):
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(404, "Interview not found.")
    return interview


def practice_feedback(turn):
    try:
        evaluation = json.loads(turn.evaluation_json or "{}")
        return evaluation.get("practice_feedback") if isinstance(evaluation, dict) else None
    except (ValueError, TypeError):
        return None


def session_payload(interview):
    turns = [{
        "turn_number": turn.turn_number, "question": turn.question,
        "answer_text": turn.answer_text, "skill": turn.skill,
        "difficulty": turn.difficulty, "decision": turn.decision,
        "id": turn.id, "turn_type": turn.turn_type,
        "changed_condition": turn.changed_condition, "parent_turn_id": turn.parent_turn_id,
        "teaching_note": turn.teaching_note if interview.mode == "practice" else None,
        **({"practice_feedback": practice_feedback(turn)}
           if interview.mode == "practice" and turn.evaluation_json else {}),
    } for turn in interview.turns]
    try:
        plan = InterviewPlan.model_validate_json(interview.interview_plan_json) if interview.interview_plan_json else None
    except ValidationError:
        # A legacy/malformed plan must not prevent reading the saved transcript.
        plan = None
    current = next((turn for turn in turns if turn["answer_text"] is None), None)
    return {
        **metadata(interview), "interview_id": interview.id,
        "plan_summary": {"role": plan.role, "focus_skills": [item.skill for item in plan.interview_focus]} if plan else None,
        "turns": turns, "current_turn": current,
        "completed": interview.status == "completed", "max_questions": MAX_QUESTIONS,
        **({key: current[key] for key in ("turn_number", "question", "skill", "difficulty")} if current else {}),
    }


def mutate(interview_id, db, engine, answer=None):
    lock = _locks[interview_id % len(_locks)]
    if not lock.acquire(blocking=False):
        if answer is None:
            return JSONResponse(status_code=202, content={"status": "starting"}, headers={"Retry-After": "2"})
        raise HTTPException(409, "An interview request is already running. Wait and reload the session.")
    try:
        interview = load_interview(db, interview_id)
        if answer is None:
            engine.start(db, interview)
        else:
            engine.answer(db, interview, answer)
        db.commit()
        db.expire_all()
        return session_payload(load_interview(db, interview_id))
    except AIServiceError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc)) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Could not save the session. Reload it before retrying.") from None
    finally:
        lock.release()


@router.post("/{interview_id}/start")
def start_interview(interview_id: int, db: Session = Depends(get_db), engine=Depends(get_interview_engine)):
    return mutate(interview_id, db, engine)


@router.post("/{interview_id}/answer")
def answer_interview(interview_id: int, answer: AnswerInput, db: Session = Depends(get_db), engine=Depends(get_interview_engine)):
    return mutate(interview_id, db, engine, answer)


@router.get("/{interview_id}/session")
def get_session(interview_id: int, db: Session = Depends(get_db)):
    return session_payload(load_interview(db, interview_id))
