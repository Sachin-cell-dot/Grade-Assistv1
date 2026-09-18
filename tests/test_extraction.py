import unittest

from tools.confidence import check_confidence
from tools.scoring import compute_score
from tools.vision import extract_marks


class ExtractionPipelineTests(unittest.TestCase):
    def test_dual_read_agreement_and_deterministic_score(self):
        reads = iter([
            {"student_name": "Aarav Mehta", "reported_total": 999, "questions": [{"question_number": 1, "extracted_mark": 4, "max_mark": 5}, {"question_number": 2, "extracted_mark": 3, "max_mark": 5}]},
            {"student_name": "Aarav Mehta", "reported_total": 999, "questions": [{"question_number": 1, "extracted_mark": 4, "max_mark": 5}, {"question_number": 2, "extracted_mark": 3, "max_mark": 5}]},
        ])
        extraction = extract_marks("unused-image.png", assessment_id=1, reader=lambda _: next(reads))
        score = compute_score(1, 7, extraction.first_read.questions)
        self.assertEqual(extraction.agreement_score, 1.0)
        self.assertEqual(score.total_score, 7.0)
        self.assertNotEqual(score.total_score, extraction.first_read.reported_total)

    def test_raw_confidence_uses_agreement_total_and_roster_match(self):
        reads = iter([
            {"student_name": "Aarav Mehta", "reported_total": 7, "questions": [{"question_number": 1, "extracted_mark": 4, "max_mark": 5}, {"question_number": 2, "extracted_mark": 3, "max_mark": 5}]},
            {"student_name": "Aarav Mehta", "reported_total": 7, "questions": [{"question_number": 1, "extracted_mark": 4, "max_mark": 5}, {"question_number": 2, "extracted_mark": 3, "max_mark": 5}]},
        ])
        extraction = extract_marks("unused-image.png", assessment_id=1, reader=lambda _: next(reads))
        score = compute_score(1, 7, extraction.first_read.questions)
        roster = [{"id": 7, "student_code": "DEMO-001", "full_name": "Aarav Mehta"}]
        confidence = check_confidence(extraction, score, roster, student_lookup=lambda _: roster[0])
        self.assertEqual(confidence.raw_confidence, 1.0)
        self.assertTrue(confidence.checks["dual_read_agreement"])
        self.assertEqual(confidence.matched_student_id, 7)
