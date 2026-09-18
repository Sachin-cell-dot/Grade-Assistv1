import json
import tempfile
import unittest
from pathlib import Path

from core.models import VisionExtraction
from database import DraftPersistenceError, canonical_question_key, get_connection, initialize_database, persist_draft_extraction


def extraction_fixture() -> VisionExtraction:
    return VisionExtraction.model_validate({"student": {"name": "Draft Student"}, "sections": [{"section_name": f"Section {section}", "section_score": {"obtained": 4, "maximum": 4}, "questions": [{"question_number": f"{section}{letter}", "student_answer": "visible answer", "individual_score": {"obtained": 1, "maximum": 1}} for letter in "abcd"]} for section in range(1, 6)], "score": {"obtained": 99, "maximum": 20}})


class DraftPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(); self.path = Path(self.tempdir.name) / "draft.db"; initialize_database(self.path)
        with get_connection(self.path) as db:
            self.student = db.execute("INSERT INTO students (student_code, full_name) VALUES ('DRAFT-1', 'Draft Student')").lastrowid
            self.assessment = db.execute("INSERT INTO assessments (title, max_score) VALUES ('Draft test', 20)").lastrowid
            self.mapping = {}
            for index in range(1, 21):
                question_id = db.execute("INSERT INTO assessment_questions (assessment_id, question_number, max_mark) VALUES (?, ?, 1)", (self.assessment, index)).lastrowid
                section, offset = divmod(index - 1, 4); self.mapping[canonical_question_key(section + 1, f"{section + 1}{'abcd'[offset]}", offset + 1)] = question_id

    def tearDown(self): self.tempdir.cleanup()

    def test_canonical_extraction_persists_as_unconfirmed_draft_idempotently(self):
        extraction = extraction_fixture(); original = extraction.model_dump(mode="json")
        result = persist_draft_extraction(extraction, assessment_id=self.assessment, student_id=self.student, source_reference="capture-001", question_id_map=self.mapping, db_path=self.path)
        repeat = persist_draft_extraction(extraction, assessment_id=self.assessment, student_id=self.student, source_reference="capture-001", question_id_map=self.mapping, db_path=self.path)
        self.assertEqual(result["computed_total"], 20); self.assertEqual(result["reported_total"], 99); self.assertTrue(repeat["idempotent"]); self.assertEqual(extraction.model_dump(mode="json"), original)
        with get_connection(self.path) as db:
            record = db.execute("SELECT grading_status, teacher_confirmed, total_score, reported_total_score, source_reference FROM grading_records").fetchone()
            sections = db.execute("SELECT COUNT(*) FROM extraction_sections").fetchone()[0]; marks = db.execute("SELECT COUNT(*) FROM extracted_marks").fetchone()[0]
        self.assertEqual((record["grading_status"], record["teacher_confirmed"], record["total_score"], record["reported_total_score"], record["source_reference"]), ("draft", 0, 20, 99, "capture-001")); self.assertEqual((sections, marks), (5, 20))

    def test_unmapped_extraction_does_not_write_partial_draft(self):
        with self.assertRaises(DraftPersistenceError): persist_draft_extraction(extraction_fixture(), assessment_id=self.assessment, student_id=self.student, source_reference="bad", question_id_map={}, db_path=self.path)
        with get_connection(self.path) as db: self.assertEqual(db.execute("SELECT COUNT(*) FROM grading_records").fetchone()[0], 0)
