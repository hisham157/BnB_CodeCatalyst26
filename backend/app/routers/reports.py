from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Interview
from ..report_schemas import PracticeReport, RecruiterReport
from ..services.gemini_service import AIServiceError
from ..services.report_service import get_report_service
from .interview_session import _locks, load_interview

router = APIRouter(prefix="/api/interviews", tags=["results"])


def stored_report(interview):
    schema = PracticeReport if interview.mode == "practice" else RecruiterReport
    try:
        report = schema.model_validate_json(interview.final_report_json)
    except ValidationError:
        raise HTTPException(500, "Stored report could not be read. The interview transcript is still available.") from None
    return {"interview_id": interview.id, "job_title": interview.job_title,
            "generated_at": interview.report_generated_at, "report": report.model_dump()}


@router.get("")
def list_interviews(db: Session = Depends(get_db)):
    interviews = db.scalars(select(Interview).order_by(Interview.created_at.desc()).limit(50))
    return [{"id": item.id, "job_title": item.job_title, "mode": item.mode, "status": item.status,
             "created_at": item.created_at, "report_ready": bool(item.final_report_json)} for item in interviews]


@router.get("/{interview_id}/report")
def get_report(interview_id: int, db: Session = Depends(get_db)):
    interview = load_interview(db, interview_id)
    if not interview.final_report_json:
        raise HTTPException(404, "Report has not been generated yet.")
    return stored_report(interview)


@router.post("/{interview_id}/finalize")
def finalize(interview_id: int, db: Session = Depends(get_db), service=Depends(get_report_service)):
    interview = load_interview(db, interview_id)
    if interview.final_report_json:
        return stored_report(interview)
    if interview.status != "completed":
        raise HTTPException(409, "Complete the interview before generating a report.")
    lock = _locks[interview_id % len(_locks)]
    if not lock.acquire(blocking=False):
        return JSONResponse(status_code=202, content={"status": "generating"}, headers={"Retry-After": "2"})
    try:
        # Reload inside the lock in case another request committed between read and acquisition.
        db.refresh(interview)
        if not interview.final_report_json:
            report = service.generate(interview)
            interview.final_report_json = report.model_dump_json()
            interview.report_generated_at = datetime.now(timezone.utc)
            db.commit()
        return stored_report(interview)
    except AIServiceError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, f"Report generation failed. {exc} Retry using the saved interview.") from None
    except (ValidationError, ValueError, TypeError):
        db.rollback()
        raise HTTPException(502, "Report generation failed validation. Your interview is saved; retry.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Could not save the report. Interview data is preserved; retry.") from None
    finally:
        lock.release()
