import json
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import IntegrityEvent, InterviewTurn
from .interview_session import load_interview

router = APIRouter(prefix="/api/interviews", tags=["integrity observations"])
_write_lock = Lock()
EventType = Literal["LOOKING_AWAY", "FACE_MISSING", "MULTIPLE_FACES", "MONITORING_UNAVAILABLE"]


class ObservationMetadata(BaseModel):
    # Explicit fields prevent frames, landmarks, or arbitrary payloads being stored.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    orientation_method: Literal["normalized_landmark_ratios"] | None = None
    monitoring_quality: Literal["heuristic", "unavailable"] | None = None
    reason: Literal["CAMERA_PERMISSION_DENIED", "CAMERA_DISCONNECTED", "CAMERA_UNAVAILABLE", "MEDIAPIPE_INITIALIZATION_FAILED", "TRACKING_FAILED", "PAGE_HIDDEN", "FRAME_GAP", "MONITORING_STOPPED", "UNSUPPORTED_BROWSER"] | None = None
    session_id: str | None = Field(default=None, max_length=80)
    end_reason: Literal["recovered", "monitoring_stopped", "page_hidden", "frame_gap", "unavailable"] | None = None
    threshold_ms: int | None = Field(default=None, ge=0, le=60000)


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    client_event_id: str | None = Field(default=None, min_length=1, max_length=80)
    event_type: EventType
    turn_number: int | None = Field(default=None, ge=1, le=6)
    started_at_seconds: float = Field(ge=0, le=31536000)
    ended_at_seconds: float | None = Field(default=None, ge=0, le=31536000)
    duration_seconds: float | None = Field(default=None, ge=0, le=31536000)
    metadata: ObservationMetadata = Field(default_factory=ObservationMetadata)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.ended_at_seconds is None:
            if self.duration_seconds is not None:
                raise ValueError("Duration requires an end time.")
        else:
            duration = self.ended_at_seconds - self.started_at_seconds
            if duration < 0:
                raise ValueError("Event end must not precede its start.")
            if self.duration_seconds is not None and abs(self.duration_seconds - duration) > 0.02:
                raise ValueError("Duration must equal end minus start.")
            self.duration_seconds = round(duration, 3)
        return self


class ExplanationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    explanation: str | None = Field(default=None, max_length=2000)


def event_payload(event):
    return {key: getattr(event, key) for key in (
        "id", "interview_id", "client_event_id", "turn_number", "event_type",
        "started_at_seconds", "ended_at_seconds", "duration_seconds",
        "occurrence_number", "candidate_explanation", "created_at",
    )} | {"metadata": json.loads(event.metadata_json or "{}")}


@router.post("/{interview_id}/integrity-events", status_code=201)
def create_event(interview_id: int, data: EventInput, db: Session = Depends(get_db)):
    # Serializes occurrence allocation for the supported single-process prototype.
    with _write_lock:
        interview = load_interview(db, interview_id)
        if interview.status not in {"in_progress", "completed"}:
            raise HTTPException(409, "Start the interview before recording observations.")
        if data.client_event_id:
            existing = db.scalar(select(IntegrityEvent).where(IntegrityEvent.interview_id == interview_id, IntegrityEvent.client_event_id == data.client_event_id))
            if existing:
                return event_payload(existing)
        if data.turn_number is not None and not db.scalar(select(InterviewTurn.id).where(InterviewTurn.interview_id == interview_id, InterviewTurn.turn_number == data.turn_number)):
            raise HTTPException(422, "The referenced interview question does not exist.")
        count = db.scalar(select(func.max(IntegrityEvent.occurrence_number)).where(IntegrityEvent.interview_id == interview_id, IntegrityEvent.event_type == data.event_type)) or 0
        event = IntegrityEvent(
            interview_id=interview_id, occurrence_number=count + 1,
            metadata_json=data.metadata.model_dump_json(exclude_none=True),
            **data.model_dump(exclude={"metadata"}),
        )
        try:
            db.add(event)
            db.commit()
            db.refresh(event)
        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(503, "Could not save the observation. Please retry.") from None
        return event_payload(event)


@router.get("/{interview_id}/integrity-events")
def list_events(interview_id: int, db: Session = Depends(get_db)):
    load_interview(db, interview_id)
    events = db.scalars(select(IntegrityEvent).where(IntegrityEvent.interview_id == interview_id).order_by(IntegrityEvent.started_at_seconds, IntegrityEvent.id))
    return [event_payload(event) for event in events]


@router.patch("/{interview_id}/integrity-events/{event_id}/explanation")
def explain_event(interview_id: int, event_id: int, data: ExplanationInput, db: Session = Depends(get_db)):
    load_interview(db, interview_id)
    event = db.scalar(select(IntegrityEvent).where(IntegrityEvent.id == event_id, IntegrityEvent.interview_id == interview_id))
    if event is None:
        raise HTTPException(404, "Integrity observation not found.")
    event.candidate_explanation = data.explanation or None
    try:
        db.commit()
        db.refresh(event)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Could not save the explanation. Please retry.") from None
    return event_payload(event)
