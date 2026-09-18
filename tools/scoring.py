"""Deterministic scoring from extracted question marks only."""
from core.models import QuestionExtraction, ScoringResult


def compute_score(assessment_id: int, student_id: int, questions: list[QuestionExtraction]) -> ScoringResult:
    """Sum question marks; deliberately never reads a model-reported total."""
    total_score = sum(question.extracted_mark or 0 for question in questions)
    max_score = sum(question.max_mark or 0 for question in questions)
    if max_score <= 0:
        raise ValueError("At least one question must include a positive max_mark")
    return ScoringResult(assessment_id=assessment_id, student_id=student_id, total_score=total_score, max_score=max_score, percentage=round(total_score * 100 / max_score, 2))
