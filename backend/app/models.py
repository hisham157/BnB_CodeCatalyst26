from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, Float, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    required_skills: Mapped[str] = mapped_column(Text, nullable=False)
    resume_filename: Mapped[str] = mapped_column(String, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String, default="recruiter", server_default="recruiter")
    interview_plan_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    turns: Mapped[list["InterviewTurn"]] = relationship(back_populates="interview", order_by="InterviewTurn.turn_number")
    status: Mapped[str] = mapped_column(String, default="created", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


class InterviewTurn(Base):
    __tablename__ = "interview_turns"
    __table_args__ = (
        UniqueConstraint("interview_id", "turn_number"),
        CheckConstraint("difficulty BETWEEN 1 AND 5"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), index=True)
    turn_number: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill: Mapped[str] = mapped_column(String)
    difficulty: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn_type: Mapped[str] = mapped_column(String, default="NORMAL", server_default="NORMAL")
    changed_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_turn_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    teaching_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    interview: Mapped[Interview] = relationship(back_populates="turns")


class IntegrityEvent(Base):
    __tablename__ = "integrity_events"
    __table_args__ = (
        UniqueConstraint("interview_id", "client_event_id"),
        UniqueConstraint("interview_id", "event_type", "occurrence_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), index=True)
    client_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    turn_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String)
    started_at_seconds: Mapped[float] = mapped_column(Float)
    ended_at_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    occurrence_number: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
