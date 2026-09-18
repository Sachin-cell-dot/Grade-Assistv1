"""Confidence-policy helpers, independent from extraction and orchestration."""

from __future__ import annotations
from difflib import SequenceMatcher
from typing import Any, Callable
import hashlib
import json

from config import get_settings
from core.models import ConfidenceResult, DualReadExtractionResult, ScoringResult
from database import get_student
from core.models import VisionExtraction


def _canonical_fields(value: VisionExtraction) -> dict[str, object]:
    """Structure-aware comparison representation; list order is meaningful."""
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


def _atoms(value: object, path: str = "") -> dict[str, object]:
    if isinstance(value, dict):
        return {key: item for name, child in value.items() for key, item in _atoms(child, f"{path}.{name}" if path else name).items()}
    if isinstance(value, list):
        return {key: item for index, child in enumerate(value) for key, item in _atoms(child, f"{path}[{index}]").items()}
    return {path: value}


def canonical_dual_read_agreement(first: VisionExtraction, second: VisionExtraction | None) -> tuple[float | None, list[str]]:
    if second is None:
        return None, ["second_read_unavailable"]
    left, right = _atoms(_canonical_fields(first)), _atoms(_canonical_fields(second))
    paths = sorted(set(left) | set(right)); disagreements = [path for path in paths if left.get(path, object()) != right.get(path, object())]
    return ((len(paths) - len(disagreements)) / len(paths) if paths else 1.0), disagreements


def evaluate_canonical_confidence(first: VisionExtraction, second: VisionExtraction | None, *, computed_total: float | None, roster: list[dict[str, Any]]) -> dict[str, Any]:
    agreement, reasons = canonical_dual_read_agreement(first, second)
    reported = first.score.obtained
    total_state = "unavailable" if reported is None or computed_total is None else ("match" if abs(reported - computed_total) < .01 else "mismatch")
    if total_state == "mismatch": reasons.append("reported_total_mismatch")
    name = first.student.name or ""; matches = sorted(((SequenceMatcher(None, name.casefold(), row.get("full_name", "").casefold()).ratio(), row) for row in roster), reverse=True, key=lambda item:item[0])
    similarity = matches[0][0] if matches else 0.0
    ambiguous = len(matches) > 1 and abs(matches[0][0] - matches[1][0]) < .01
    roster_state = "unavailable" if not roster else ("ambiguous" if ambiguous else ("matched" if similarity >= get_settings().name_fuzzy_match_threshold else "unresolved"))
    matched = matches[0][1].get("id") if roster_state == "matched" else None
    if roster_state != "matched": reasons.append(f"roster_{roster_state}")
    uncertainty = list(first.uncertain_items) + [item for section in first.sections for item in section.uncertain_fields] + [item for question in first.questions for item in question.uncertain_fields]
    if uncertainty: reasons.append("canonical_uncertainty_present")
    available = [agreement] if agreement is not None else []
    if total_state != "unavailable": available.append(1.0 if total_state == "match" else 0.0)
    if roster_state != "unavailable": available.append(similarity if roster_state == "matched" else 0.0)
    available.append(0.5 if uncertainty else 1.0)
    coverage = len(available) / 4
    raw = (sum(available) / len(available)) * coverage
    safety = [name for name, condition in {"second_read_unavailable": second is None, "total_mismatch": total_state == "mismatch", "identity_unresolved": roster_state in {"unresolved", "ambiguous"}, "canonical_uncertainty": bool(uncertainty)}.items() if condition]
    return {"raw_confidence": raw, "evidence_coverage": coverage, "dual_read_agreement": agreement, "total_cross_check": total_state, "roster_match": {"status": roster_state, "similarity": similarity, "matched_student_id": matched}, "uncertainty_signals": uncertainty, "reasons": reasons, "safety_signals": safety, "evidence": {"computed_total": computed_total, "reported_total": reported, "floor": get_settings().escalation_floor, "adaptive_threshold": get_settings().auto_approve_threshold}}


def persist_canonical_confidence(grading_record_id: int, result: dict[str, Any], db_path=None) -> dict[str, Any]:
    from database.db import get_connection, initialize_database
    initialize_database(db_path); encoded = json.dumps(result, sort_keys=True); fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    with get_connection(db_path) as db:
        existing = db.execute("SELECT id FROM confidence_evaluations WHERE grading_record_id=? AND evidence_fingerprint=?", (grading_record_id, fingerprint)).fetchone()
        if existing: return {"id": existing["id"], "idempotent": True}
        cursor = db.execute("INSERT INTO confidence_evaluations (grading_record_id,evidence_fingerprint,raw_confidence,evidence_coverage,dual_read_agreement,total_cross_check,roster_match_json,uncertainty_signals_json,reasons_json,evidence_json) VALUES (?,?,?,?,?,?,?,?,?,?)", (grading_record_id,fingerprint,result["raw_confidence"],result["evidence_coverage"],result["dual_read_agreement"],result["total_cross_check"],json.dumps(result["roster_match"]),json.dumps(result["uncertainty_signals"]),json.dumps(result["reasons"]),encoded))
    return {"id": cursor.lastrowid, "idempotent": False}


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
