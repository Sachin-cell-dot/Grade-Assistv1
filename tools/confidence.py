"""Confidence-policy helpers, independent from extraction and orchestration."""

from __future__ import annotations
from difflib import SequenceMatcher
from typing import Any, Callable

from config import get_settings
from core.models import ConfidenceResult, DualReadExtractionResult, ScoringResult
from database import get_student


def clamp_auto_approve_threshold(value: float, minimum: float, maximum: float) -> float:
    """Apply only adaptive bounds; escalation is a separate fixed rail."""
    if not 0 <= minimum <= maximum <= 1:
        raise ValueError("threshold clamps must satisfy 0 <= minimum <= maximum <= 1")
    return max(minimum, min(value, maximum))


def adjust_after_confirmed_correct_escalations(
    current_threshold: float,
    confirmed_correct_count: int,
    minimum: float,
    maximum: float,
    tighten_step: float,
) -> float:
    """Lower an adaptive threshold cautiously while preserving its configured floor."""
    if confirmed_correct_count < 0 or tighten_step < 0:
        raise ValueError("confirmation count and reduction must be non-negative")
    return clamp_auto_approve_threshold(
        current_threshold - confirmed_correct_count * tighten_step,
        minimum,
        maximum,
    )


def check_confidence(
    extraction: DualReadExtractionResult,
    score: ScoringResult,
    roster: list[dict[str, Any]],
    student_lookup: Callable[[str], dict[str, Any] | None] = get_student,
) -> ConfidenceResult:
    """Return raw evidence confidence only; orchestration owns confidence bands."""
    settings = get_settings()
    name = extraction.first_read.student_name or extraction.second_read.student_name or ""
    matched_id: int | None = None
    name_score = 0.0
    for roster_entry in roster:
        student = student_lookup(roster_entry["student_code"]) or roster_entry
        candidate = student.get("full_name", "")
        similarity = SequenceMatcher(None, name.casefold(), candidate.casefold()).ratio()
        if similarity > name_score:
            name_score, matched_id = similarity, student.get("id")
    reported = [read.reported_total for read in (extraction.first_read, extraction.second_read)]
    total_cross_check = sum(value is not None and abs(value - score.total_score) < 0.01 for value in reported) / len(reported)
    raw = min(extraction.agreement_score, total_cross_check, name_score)
    return ConfidenceResult(
        raw_confidence=raw,
        dual_read_agreement=extraction.agreement_score,
        total_cross_check=total_cross_check,
        name_match_score=name_score,
        matched_student_id=matched_id,
        checks={
            "dual_read_agreement": extraction.agreement_score >= settings.dual_read_agreement_min,
            "name_fuzzy_match": name_score >= settings.name_fuzzy_match_threshold,
            "escalation_floor": raw >= settings.escalation_floor,
            "auto_approve_threshold": raw >= settings.auto_approve_threshold,
        },
    )
