"""Evidence aggregation and grounded report synthesis; no integrity data enters this service."""
import json
from statistics import mean

import numpy as np

from ..report_schemas import (AdaptationEvidence, ExtractedClaims, PracticeImprovementEvidence,
                              PracticeReport, RecruiterReport, ReportNarrative, ResumeClaimEvidence,
                              SkillEvidence)
from ..schemas import InterviewPlan
from .gemini_service import AIServiceError, GeminiService
from .interview_engine import normalized
from .rag_service import RagService, chunk_text

RUBRIC_FIELDS = ("relevance_score", "specificity_score", "depth_score", "evidence_score")


def aggregate_skills(interview):
    names = list(json.loads(interview.required_skills))
    if interview.interview_plan_json:
        names += [item.skill for item in InterviewPlan.model_validate_json(interview.interview_plan_json).interview_focus]
    names += [turn.skill for turn in interview.turns]
    names = list({normalized(name): name for name in names}.values())
    evidence = []
    for skill in names:
        scores, refs = [], []
        for turn in interview.turns:
            if normalized(turn.skill) != normalized(skill) or not turn.answer_text or not turn.evaluation_json:
                continue
            try:
                rubric = json.loads(turn.evaluation_json)
                values = [rubric[field] for field in RUBRIC_FIELDS]
                if not all(type(value) in (int, float) and 0 <= value <= 5 for value in values):
                    continue
            except (ValueError, KeyError, TypeError):
                continue
            scores.append(mean(values))
            refs.append(turn.turn_number)
        score = mean(scores) if scores else None
        level = 0 if score is None else 5 if score >= 4.5 else 4 if score >= 4 else 3 if score >= 2.5 else 2 if score >= 1 else 1
        label = "NOT_ASSESSED" if level == 0 else "STRONG" if level >= 4 else "MODERATE" if level == 3 else "LIMITED_EVIDENCE"
        evidence.append(SkillEvidence(skill=skill, evidence_level=level, label=label, supporting_turns=refs,
            why="Not sufficiently assessed." if not refs else "Evidence level aggregates the four stored rubric dimensions across the referenced answers.",
            remaining_gap="Further role-relevant questions are needed."))
    return evidence


def retrieve_claim_turns(claims, turns, rag):
    """Rank answer chunks, not candidates. The conservative cutoff is a retrieval heuristic."""
    answered = [turn for turn in turns if turn.answer_text]
    if not claims or not answered:
        return [[] for _ in claims]
    chunks = [(turn.turn_number, part) for turn in answered for part in chunk_text(turn.answer_text, size=650, overlap=80)]
    try:
        vectors = rag.encode([part for _, part in chunks])
        queries = rag.encode([claim.claim_text for claim in claims])
    except Exception as exc:
        raise AIServiceError("Local claim matching is unavailable. Check the embedding model and retry.") from exc
    matches = []
    for query in queries:
        scores = vectors @ query
        selected = []
        for index in np.argsort(-scores).tolist():
            number = chunks[index][0]
            if scores[index] >= 0.25 and number not in selected:
                selected.append(number)
            if len(selected) == 2:
                break
        matches.append(selected)
    return matches


def challenge_pairs(interview, kind):
    by_id = {turn.id: turn for turn in interview.turns}
    pairs = []
    for turn in interview.turns:
        original = by_id.get(turn.parent_turn_id)
        if turn.turn_type == kind and original and original.answer_text and turn.answer_text:
            pairs.append((original, turn))
    return pairs


def report_error():
    return AIServiceError("Report evidence references were inconsistent. Your interview is saved; retry report generation.", 502)


class ReportService:
    def __init__(self, ai=None, rag=None):
        self.ai = ai or GeminiService()
        self.rag = rag or RagService()

    def generate(self, interview):
        self.ai.ensure_configured()
        skills = aggregate_skills(interview)
        turns = [turn for turn in interview.turns if turn.answer_text]
        valid_refs = {turn.turn_number for turn in turns}
        if not valid_refs:
            raise AIServiceError("No answered questions are available for this report.", 409)
        claims = []
        if interview.mode == "recruiter":
            extracted = self.ai.generate(ExtractedClaims,
                "Extract up to 3-5 significant job-relevant professional claims, fewer if unsupported. "
                "claim_text MUST be an exact contiguous resume excerpt. Only projects, metrics, responsibilities, "
                "skill experience or professional leadership. Exclude identity, personal/protected traits and hobbies. "
                "Choose related_skill exactly from allowed_skills. Never invent claims.",
                {"resume": interview.resume_text, "role": interview.job_title, "job_description": interview.job_description,
                 "allowed_skills": [item.skill for item in skills]})
            allowed_skills = {normalized(item.skill) for item in skills}
            for claim in extracted.claims:
                if normalized(claim.claim_text) not in normalized(interview.resume_text) or normalized(claim.related_skill) not in allowed_skills:
                    raise report_error()
                if claim.claim_text not in [item.claim_text for item in claims]:
                    claims.append(claim)
        matches = retrieve_claim_turns(claims, turns, self.rag)
        adaptation = challenge_pairs(interview, "CHANGE_CONSTRAINT")
        teaching = challenge_pairs(interview, "TEACH_NEW_CHALLENGE") if interview.mode == "practice" else []
        context = {
            "mode": interview.mode, "role": interview.job_title, "job_description": interview.job_description,
            "skill_aggregates": [item.model_dump() for item in skills],
            "turns": [{"turn_number": turn.turn_number, "question": turn.question, "answer": turn.answer_text,
                       "skill": turn.skill, "turn_type": turn.turn_type, "changed_condition": turn.changed_condition,
                       "teaching_note": turn.teaching_note if interview.mode == "practice" else None} for turn in turns],
            "claims": [{"claim_index": index, **claim.model_dump(), "retrieved_turns": matches[index]} for index, claim in enumerate(claims)],
            "adaptation_pairs": [[a.turn_number, b.turn_number] for a, b in adaptation],
            "teaching_pairs": [[a.turn_number, b.turn_number] for a, b in teaching],
        }
        narrative = self.ai.generate(ReportNarrative,
            "Synthesize a concise evidence report. Every summary, strength, gap and next step must cite supporting turn numbers. "
            "Use only the supplied answers; describe limitations, not assumed ability. Do not infer protected traits, hiring suitability, "
            "honesty or personality. No hiring/rejection decisions. Scores and labels are already computed, do not invent or change them. "
            "Give exactly one skill_note per assessed skill, referencing only that skill's aggregate supporting_turns; omit NOT_ASSESSED skills. "
            "For each claim give one claim_note. Cite only its retrieved_turns and only if the answer actually discusses the claim. "
            "Similarity retrieves relevance, never truth. SUPPORTED_BY_EXPLANATION means explained, NOT independently verified. "
            "Use NOT_ASSESSED with empty references when no relevant explanation exists, otherwise explain any remaining clarification. "
            "Do not add claims. Adaptation/practice_improvement must be null unless the corresponding pair exists; "
            "if present cite its challenge_turn and interpret only the original and revised answers. "
            "Describe observed change or lack of improvement, never an adaptability or learning score. "
            "Practice next_steps are actionable exercises; recruiter next_steps are follow-up questions. "
            "No recruiter suitability language in practice mode. No coaching in recruiter assessments. "
            "Do not output hidden reasoning, only concise evidence explanations.", context)
        for statement in narrative.summary + narrative.strengths + narrative.gaps + narrative.next_steps:
            if not set(statement.supporting_turns) <= valid_refs:
                raise report_error()
        notes = {normalized(note.skill): note for note in narrative.skill_notes}
        assessed = {normalized(item.skill) for item in skills if item.evidence_level}
        if set(notes) != assessed or len(notes) != len(narrative.skill_notes):
            raise report_error()
        for skill in skills:
            if not skill.evidence_level:
                continue
            note = notes[normalized(skill.skill)]
            if not note.supporting_turns or not set(note.supporting_turns) <= set(skill.supporting_turns):
                raise report_error()
            skill.why, skill.remaining_gap = note.why, note.remaining_gap
        claim_notes = {note.claim_index: note for note in narrative.claim_notes}
        if set(claim_notes) != set(range(len(claims))) or len(claim_notes) != len(narrative.claim_notes):
            raise report_error()
        claim_evidence = []
        for index, claim in enumerate(claims):
            note = claim_notes[index]
            if not set(note.supporting_turns) <= set(matches[index]):
                raise report_error()
            if (note.status == "NOT_ASSESSED") != (not note.supporting_turns):
                raise report_error()
            claim_evidence.append(ResumeClaimEvidence(**claim.model_dump(), **note.model_dump(exclude={"claim_index"})))
        adaptation_evidence = self.pair_evidence(narrative.adaptation, adaptation, False)
        improvement = self.pair_evidence(narrative.practice_improvement, teaching, True)
        common = dict(summary=narrative.summary, skill_evidence=skills, adaptation_evidence=adaptation_evidence,
                      strengths=narrative.strengths, gaps=narrative.gaps)
        if interview.mode == "practice":
            return PracticeReport(**common, practice_improvement=improvement, practice_recommendations=narrative.next_steps)
        return RecruiterReport(**common, resume_claims=claim_evidence, areas_for_follow_up=narrative.next_steps)

    @staticmethod
    def pair_evidence(note, pairs, practice):
        if not pairs:
            if note is not None:
                raise report_error()
            return None
        if note is None:
            raise report_error()
        pair = next(((a, b) for a, b in pairs if b.turn_number == note.challenge_turn), None)
        if pair is None:
            raise report_error()
        original, challenge = pair
        common = dict(**note.model_dump(), original_turn=original.turn_number)
        if practice:
            return PracticeImprovementEvidence(**common, first_attempt=original.answer_text,
                teaching_note=challenge.teaching_note, new_question=challenge.question, second_attempt=challenge.answer_text)
        return AdaptationEvidence(**common, original_approach=original.answer_text,
            changed_condition=challenge.changed_condition, revised_approach=challenge.answer_text)


service = ReportService()


def get_report_service():
    return service
