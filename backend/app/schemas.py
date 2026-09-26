from datetime import datetime

from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class InterviewInput(BaseModel):
    job_title: str = Field(min_length=1)
    job_description: str = ""
    required_skills: list[str] = Field(default_factory=list)
    mode: Literal["recruiter", "practice"] = "recruiter"

    @model_validator(mode="after")
    def recruiter_requirements(self):
        if self.mode == "recruiter" and (not self.job_description or not self.required_skills):
            raise ValueError("Recruiter interviews require a job description and at least one required skill.")
        return self

    @field_validator("job_title", "job_description", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("required_skills")
    @classmethod
    def clean_skills(cls, skills):
        cleaned = [skill.strip() for skill in skills]
        if any(not skill for skill in cleaned):
            raise ValueError("Required skills cannot contain empty values.")
        return list(dict.fromkeys(cleaned))


class InterviewCreated(BaseModel):
    id: int
    job_title: str
    required_skills: list[str]
    resume_filename: str
    resume_character_count: int
    status: str
    mode: Literal["recruiter", "practice"]


class InterviewMetadata(InterviewCreated):
    job_description: str
    created_at: datetime


class StructuredModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class FocusSkill(StructuredModel):
    skill: str = Field(min_length=1, max_length=120)
    priority: int = Field(ge=1, le=5)


class InterviewPlan(StructuredModel):
    role: str = Field(min_length=1, max_length=200)
    interview_focus: list[FocusSkill] = Field(min_length=1, max_length=8)
    candidate_context_summary: str = Field(min_length=1, max_length=1500)
    recommended_starting_difficulty: int = Field(ge=1, le=5)


class FirstQuestion(StructuredModel):
    question: str = Field(min_length=1, max_length=2000)
    skill: str = Field(min_length=1, max_length=120)
    difficulty: int = Field(ge=1, le=5)


Decision = Literal["PROBE_DEEPER", "INCREASE_DIFFICULTY", "DECREASE_DIFFICULTY", "CLARIFY", "SWITCH_TOPIC", "CHANGE_CONSTRAINT", "TEACH_AND_RETRY"]


class TurnDecision(StructuredModel):
    relevance_score: int = Field(ge=0, le=5)
    specificity_score: int = Field(ge=0, le=5)
    depth_score: int = Field(ge=0, le=5)
    evidence_score: int = Field(ge=0, le=5)
    decision: Decision
    decision_reason: str = Field(min_length=1, max_length=500)
    next_skill: str = Field(min_length=1, max_length=120)
    next_difficulty: int = Field(ge=1, le=5)
    next_question: str = Field(min_length=1, max_length=2000)
    practice_feedback: str = Field(min_length=1, max_length=350)
    changed_condition: str | None = Field(default=None, max_length=500)
    teaching_note: str | None = Field(default=None, max_length=350)
    testable_approach: bool = False
    conceptual_gap: str | None = Field(default=None, max_length=350)


class AnswerInput(StructuredModel):
    answer_text: str = Field(min_length=1, max_length=20000)
    # Clients should supply this to prevent retries from answering a subsequent turn.
    turn_number: int | None = Field(default=None, ge=1, le=6)
