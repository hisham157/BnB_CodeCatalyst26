import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Interview
from ..schemas import InterviewCreated, InterviewInput, InterviewMetadata
from ..services.document_parser import DocumentExtractionError, extract_resume_text

router = APIRouter(prefix="/api/interviews", tags=["interviews"])
MAX_RESUME_BYTES = 5 * 1024 * 1024


def metadata(interview: Interview) -> dict:
    return {
        "id": interview.id,
        "job_title": interview.job_title,
        "job_description": interview.job_description,
        "required_skills": json.loads(interview.required_skills),
        "resume_filename": interview.resume_filename,
        "resume_character_count": len(interview.resume_text),
        "status": interview.status,
        "mode": interview.mode,
        "created_at": interview.created_at,
    }


@router.post("", response_model=InterviewCreated, status_code=201)
def create_interview(
    job_title: str = Form(...),
    job_description: str = Form(""),
    required_skills: str = Form("[]"),
    mode: str = Form("recruiter"),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        skills = json.loads(required_skills)
    except json.JSONDecodeError:
        raise HTTPException(422, "Required skills must be a JSON array of strings.")
    try:
        data = InterviewInput(
            job_title=job_title, job_description=job_description, required_skills=skills, mode=mode
        )
    except ValidationError as exc:
        messages = [f"{error['loc'][0] if error['loc'] else 'Input'}: {error['msg']}" for error in exc.errors()]
        raise HTTPException(422, "; ".join(messages)) from exc

    filename = (resume.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    if Path(filename).suffix.lower() not in {".pdf", ".docx"}:
        raise HTTPException(400, "Unsupported resume type. Upload a PDF or DOCX file.")
    file_bytes = resume.file.read(MAX_RESUME_BYTES + 1)
    if len(file_bytes) > MAX_RESUME_BYTES:
        raise HTTPException(413, "Resume must be 5 MB or smaller.")
    try:
        resume_text = extract_resume_text(filename, file_bytes)
    except DocumentExtractionError as exc:
        raise HTTPException(400, str(exc)) from exc

    interview = Interview(
        job_title=data.job_title,
        job_description=data.job_description,
        required_skills=json.dumps(data.required_skills),
        resume_filename=filename,
        resume_text=resume_text,
        mode=data.mode,
    )
    try:
        db.add(interview)
        db.commit()
        db.refresh(interview)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(500, "Could not save the interview. Please try again.") from exc
    return metadata(interview)


@router.get("/{interview_id}", response_model=InterviewMetadata)
def get_interview(interview_id: int, db: Session = Depends(get_db)):
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(404, "Interview not found.")
    return metadata(interview)
