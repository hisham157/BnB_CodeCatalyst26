from typing import Literal

from pydantic import Field, model_validator

from .schemas import StructuredModel

EvidenceLabel = Literal["STRONG", "MODERATE", "LIMITED_EVIDENCE", "NOT_ASSESSED"]
ClaimStatus = Literal["SUPPORTED_BY_EXPLANATION", "NEEDS_CLARIFICATION", "NOT_ASSESSED"]


class EvidenceStatement(StructuredModel):
    text: str = Field(min_length=1, max_length=700)
    supporting_turns: list[int] = Field(min_length=1, max_length=6)


class SkillNote(StructuredModel):
    skill: str = Field(min_length=1, max_length=120)
    why: str = Field(min_length=1, max_length=800)
    supporting_turns: list[int] = Field(max_length=6)
    remaining_gap: str = Field(min_length=1, max_length=600)


class SkillEvidence(SkillNote):
    evidence_level: int = Field(ge=0, le=5)
    label: EvidenceLabel

    @model_validator(mode="after")
    def consistent_level(self):
        expected = "NOT_ASSESSED" if self.evidence_level == 0 else "LIMITED_EVIDENCE" if self.evidence_level <= 2 else "MODERATE" if self.evidence_level == 3 else "STRONG"
        if self.label != expected or (self.evidence_level == 0 and self.supporting_turns):
            raise ValueError("Evidence level, label and references must agree.")
        return self


class ResumeClaim(StructuredModel):
    claim_text: str = Field(min_length=1, max_length=500)
    claim_type: Literal["PROJECT", "METRIC", "RESPONSIBILITY", "SKILL_EXPERIENCE", "LEADERSHIP"]
    related_skill: str = Field(min_length=1, max_length=120)


class ExtractedClaims(StructuredModel):
    claims: list[ResumeClaim] = Field(max_length=5)


class ClaimInterpretation(StructuredModel):
    claim_index: int = Field(ge=0, le=4)
    status: ClaimStatus
    evidence: str = Field(min_length=1, max_length=700)
    supporting_turns: list[int] = Field(max_length=6)
    remaining_gap: str = Field(min_length=1, max_length=600)


class ResumeClaimEvidence(ResumeClaim):
    status: ClaimStatus
    evidence: str
    supporting_turns: list[int]
    remaining_gap: str


class PairInterpretation(StructuredModel):
    challenge_turn: int = Field(ge=2, le=6)
    interpretation: str = Field(min_length=1, max_length=700)


class AdaptationEvidence(PairInterpretation):
    original_turn: int
    original_approach: str
    changed_condition: str
    revised_approach: str


class PracticeImprovementEvidence(PairInterpretation):
    original_turn: int
    first_attempt: str
    teaching_note: str
    new_question: str
    second_attempt: str


class ReportNarrative(StructuredModel):
    summary: list[EvidenceStatement] = Field(max_length=3)
    skill_notes: list[SkillNote] = Field(max_length=30)
    claim_notes: list[ClaimInterpretation] = Field(max_length=5)
    adaptation: PairInterpretation | None = None
    practice_improvement: PairInterpretation | None = None
    strengths: list[EvidenceStatement] = Field(max_length=5)
    gaps: list[EvidenceStatement] = Field(max_length=5)
    next_steps: list[EvidenceStatement] = Field(max_length=5)


class ReportBase(StructuredModel):
    version: int = 1
    summary: list[EvidenceStatement]
    skill_evidence: list[SkillEvidence]
    adaptation_evidence: AdaptationEvidence | None = None
    strengths: list[EvidenceStatement]
    gaps: list[EvidenceStatement]


class RecruiterReport(ReportBase):
    mode: Literal["recruiter"] = "recruiter"
    resume_claims: list[ResumeClaimEvidence]
    areas_for_follow_up: list[EvidenceStatement]


class PracticeReport(ReportBase):
    mode: Literal["practice"] = "practice"
    practice_improvement: PracticeImprovementEvidence | None = None
    practice_recommendations: list[EvidenceStatement]
