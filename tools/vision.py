"""Dual-read assessment extraction using the configured local Ollama model."""
from __future__ import annotations
from math import isclose
from pathlib import Path
from typing import Any, Callable
from core.models import DualReadExtractionResult, ExtractionResult, QuestionExtraction
from services.ollama_service import extract_mark_read

def _to_result(payload: dict[str, Any], source_path: str, assessment_id: int | None) -> ExtractionResult:
    questions = [QuestionExtraction(question_number=item["question_number"], extracted_mark=item.get("extracted_mark"), max_mark=item.get("max_mark"), confidence=0.0, raw_text=item.get("raw_text"), evidence={"source": "ollama"}) for item in payload.get("questions", [])]
    return ExtractionResult(assessment_id=assessment_id, source_path=source_path, student_name=payload.get("student_name"), reported_total=payload.get("reported_total"), questions=questions)

def _same(left: Any, right: Any) -> float:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(isclose(left, right, abs_tol=0.01))
    return float(str(left or "").strip().casefold() == str(right or "").strip().casefold())

def extract_marks(image_path: str | Path, assessment_id: int | None = None, reader: Callable[[str | Path], dict[str, Any]] = extract_mark_read) -> DualReadExtractionResult:
    """Run two independent reads of the same image and report per-field agreement."""
    first = _to_result(reader(image_path), str(image_path), assessment_id)
    second = _to_result(reader(image_path), str(image_path), assessment_id)
    agreement = {"student_name": _same(first.student_name, second.student_name), "reported_total": _same(first.reported_total, second.reported_total)}
    first_questions, second_questions = ({q.question_number: q for q in result.questions} for result in (first, second))
    for number in sorted(set(first_questions) | set(second_questions)):
        left, right = first_questions.get(number), second_questions.get(number)
        agreement[f"question_{number}_mark"] = _same(left.extracted_mark if left else None, right.extracted_mark if right else None)
        agreement[f"question_{number}_max"] = _same(left.max_mark if left else None, right.max_mark if right else None)
    return DualReadExtractionResult(first_read=first, second_read=second, field_agreement=agreement, agreement_score=sum(agreement.values()) / len(agreement) if agreement else 0.0)
