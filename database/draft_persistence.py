"""Persistence for unconfirmed, canonical VisionExtraction drafts only."""
from __future__ import annotations

import json
from pathlib import Path

from core.models import QuestionExtraction, VisionExtraction
from tools.scoring import compute_score
from .db import get_connection, initialize_database


class DraftPersistenceError(ValueError):
    pass


def canonical_question_key(section_index: int, question_number: str | None, question_index: int) -> str:
    return f"{section_index}:{question_number if question_number is not None else '#' + str(question_index)}"


def persist_draft_extraction(
    extraction: VisionExtraction,
    *,
    assessment_id: int,
    student_id: int,
    source_reference: str,
    question_id_map: dict[str, int],
    db_path: Path | None = None,
) -> dict[str, object]:
    """Persist one validated extraction atomically; never updates student history."""
    if not source_reference.strip():
        raise DraftPersistenceError("source_reference is required for draft provenance")
    payload = extraction.model_dump(mode="json", by_alias=True)
    evidence_rows: list[tuple[int, int, object, str, str, str]] = []
    scoring_questions: list[QuestionExtraction] = []
    for section_index, section in enumerate(extraction.sections, start=1):
        for question_index, question in enumerate(section.questions, start=1):
            key = canonical_question_key(section_index, question.question_number, question_index)
            question_id = question_id_map.get(key)
            if question_id is None:
                raise DraftPersistenceError(f"No assessment question mapping for canonical question '{key}'")
            if question.individual_score and question.individual_score.obtained is not None and question.individual_score.maximum is not None:
                scoring_questions.append(QuestionExtraction(question_number=len(scoring_questions) + 1, extracted_mark=question.individual_score.obtained, max_mark=question.individual_score.maximum, confidence=0.0))
            evidence_rows.append((section_index, question_id, question, key, str(question.question_number) if question.question_number is not None else "", json.dumps(question.model_dump(mode="json"))))
    initialize_database(db_path)
    with get_connection(db_path) as connection:
        assessment = connection.execute("SELECT max_score FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
        if not assessment:
            raise DraftPersistenceError("assessment_id does not exist")
        existing = connection.execute("SELECT id, extraction_payload_json FROM grading_records WHERE assessment_id = ? AND source_reference = ?", (assessment_id, source_reference)).fetchone()
        payload_json = json.dumps(payload, sort_keys=True)
        if existing:
            if existing["extraction_payload_json"] != payload_json:
                raise DraftPersistenceError("source_reference already belongs to different extraction evidence")
            return {"grading_record_id": existing["id"], "idempotent": True}
        computed = compute_score(assessment_id, student_id, scoring_questions) if scoring_questions else None
        try:
            cursor = connection.execute("INSERT INTO grading_records (student_id, assessment_id, total_score, max_score, grading_status, reported_total_score, reported_max_score, source_reference, extraction_payload_json, extracted_student_name, teacher_confirmed) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, 0)", (student_id, assessment_id, computed.total_score if computed else None, assessment["max_score"], extraction.score.obtained, extraction.score.maximum, source_reference, payload_json, extraction.student.name))
        except Exception as error:
            raise DraftPersistenceError("draft already exists for this student and assessment") from error
        record_id = cursor.lastrowid
        section_ids: dict[int, int] = {}
        for section_index, section in enumerate(extraction.sections, start=1):
            cursor = connection.execute("INSERT INTO extraction_sections (grading_record_id, section_index, section_name, reported_score, reported_max_score, uncertain_fields_json) VALUES (?, ?, ?, ?, ?, ?)", (record_id, section_index, section.section_name, section.section_score.obtained if section.section_score else None, section.section_score.maximum if section.section_score else None, json.dumps(section.uncertain_fields)))
            section_ids[section_index] = cursor.lastrowid
        for section_index, question_id, question, key, number, evidence_json in evidence_rows:
            score = question.individual_score
            connection.execute("INSERT INTO extracted_marks (grading_record_id, assessment_question_id, extracted_mark, extraction_source, raw_text, extraction_section_id, source_question_key, source_question_number, evidence_json, teacher_confirmed) VALUES (?, ?, ?, 'canonical_vision', ?, ?, ?, ?, ?, 0)", (record_id, question_id, score.obtained if score else None, question.student_answer, section_ids[section_index], key, number, evidence_json))
    return {"grading_record_id": record_id, "idempotent": False, "computed_total": computed.total_score if computed else None, "reported_total": extraction.score.obtained, "draft": True, "question_count": len(evidence_rows)}
