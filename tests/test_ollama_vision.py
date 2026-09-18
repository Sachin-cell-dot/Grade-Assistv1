import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from services.ollama_service import (ImageNotFoundError,
                                     OllamaVisionService, UnsupportedImageTypeError,
                                     VISION_SCHEMA, VisionEmptyResponseError, VisionJSONExtractionError, VisionOllamaConnectionError, VisionOllamaTimeoutError, VisionSchemaValidationError, VisionTruncatedResponseError, _clean_json,
                                     _parse_extraction, _validate_image)

class OllamaVisionServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.image = Path(self.directory.name) / "sheet.jpeg"
        self.image.write_bytes(b"image bytes")

    def tearDown(self): self.directory.cleanup()

    def test_supported_file_validation(self): self.assertEqual(_validate_image(self.image), self.image)

    def test_unsupported_file_rejection(self):
        unsupported = self.image.with_suffix(".pdf"); unsupported.write_bytes(b"x")
        with self.assertRaises(UnsupportedImageTypeError): _validate_image(unsupported)

    def test_missing_file_rejection(self):
        with self.assertRaises(ImageNotFoundError): _validate_image(self.image.with_name("missing.png"))

    def test_markdown_json_cleanup_and_validation(self):
        payload = {"student": {"name": "Demo Student", "class": None, "date": None, "subject": "Math"}, "questions": [], "score": {"obtained": None, "maximum": None}, "teacher_comments": [], "uncertain_items": []}
        response = Mock(status_code=200); response.raise_for_status.return_value = None; response.json.return_value = {"response": f"```json\n{json.dumps(payload)}\n```"}
        session = Mock(); session.post.return_value = response
        result = OllamaVisionService(session=session).extract(self.image)
        self.assertEqual(result.student.name, "Demo Student")
        self.assertEqual(_clean_json("```json\n{}\n```"), "{}")
        self.assertNotIn(b"image bytes", str(session.post.call_args).encode())
        self.assertEqual(session.post.call_args.kwargs["json"]["format"], VISION_SCHEMA)
        self.assertEqual(session.post.call_args.kwargs["json"]["options"]["num_predict"], 4096)
        self.assertEqual(session.post.call_args.kwargs["json"]["options"]["num_ctx"], 8192)

    def test_whitespace_and_leading_prose_fenced_json(self):
        payload = {"student": {}, "questions": [], "score": {}, "teacher_comments": [], "uncertain_items": []}
        self.assertEqual(_parse_extraction(" \n```json\n" + json.dumps(payload) + "\n```\n").questions, [])
        self.assertEqual(_parse_extraction("Here is the extraction:\n```json\n" + json.dumps(payload) + "\n```").teacher_comments, [])

    def test_empty_response_has_specific_error(self):
        with self.assertRaises(VisionEmptyResponseError): _parse_extraction("  ")

    def test_ambiguous_json_objects_are_rejected(self):
        with self.assertRaises(VisionJSONExtractionError): _parse_extraction('{"student": {}} {"student": {}}')

    def test_connection_and_timeout_errors_are_specific(self):
        session = Mock(); session.post.side_effect = __import__("requests").ConnectionError("offline")
        with self.assertRaises(VisionOllamaConnectionError): OllamaVisionService(session=session).extract(self.image)
        session.post.side_effect = __import__("requests").Timeout("slow")
        with self.assertRaises(VisionOllamaTimeoutError): OllamaVisionService(session=session).extract(self.image)

    def test_malformed_response_rejection(self):
        response = Mock(status_code=200); response.raise_for_status.return_value = None; response.json.return_value = {"response": "not-json"}
        session = Mock(); session.post.return_value = response
        with self.assertRaises(VisionJSONExtractionError): OllamaVisionService(session=session).extract(self.image)

    def test_qwen_equivalent_types_are_normalized_to_canonical_schema(self):
        payload = {"student": {}, "questions": [{"question_number": 1, "question_text": "Q", "student_answer": ["A", "B"], "working_steps": None, "teacher_mark": "tick", "marks_awarded": None, "confidence": 0.8}], "score": {"obtained": 14, "maximum": 20}, "teacher_comments": "Needs practice", "uncertain_items": []}
        result = _parse_extraction("Visible worksheet facts:\n" + json.dumps(payload))
        self.assertEqual(result.questions[0].question_number, "1")
        self.assertEqual(result.questions[0].working_steps, [])
        self.assertEqual(result.questions[0].student_answer, "A\nB")
        self.assertEqual(result.score.obtained, 14.0)
        self.assertEqual(result.teacher_comments, ["Needs practice"])

    def test_granular_subquestions_keep_section_scores_separate(self):
        payload = {"student": {"name": "Demo Student"}, "sections": [{"section_name": "Addition", "section_score": {"obtained": 3, "maximum": 4}, "questions": [{"question_number": "1a", "question_text": "23 + 17", "student_answer": "40", "working_steps": [], "teacher_marking": {"marking_type": "tick", "visible_text": "✓"}, "individual_score": None, "uncertain_fields": []}, {"question_number": "1b", "question_text": "56 + 28", "student_answer": "84", "working_steps": [], "teacher_marking": {"marking_type": "tick", "visible_text": "✓"}, "individual_score": None, "uncertain_fields": []}, {"question_number": "1c", "question_text": "45 + 36", "student_answer": "81", "working_steps": [], "teacher_marking": {"marking_type": "tick", "visible_text": "✓"}, "individual_score": None, "uncertain_fields": []}, {"question_number": "1d", "question_text": "78 + 14", "student_answer": "100", "working_steps": [], "teacher_marking": {"marking_type": "cross", "visible_text": "✗"}, "individual_score": None, "uncertain_fields": ["individual_mark_not_visible"]}]}], "score": {"obtained": 14, "maximum": 20}, "teacher_comments": [], "uncertain_items": []}
        result = _parse_extraction(json.dumps(payload))
        addition = result.sections[0]
        self.assertEqual(addition.section_score.obtained, 3.0)
        self.assertEqual(addition.section_score.maximum, 4.0)
        self.assertEqual([item.question_number for item in addition.questions], ["1a", "1b", "1c", "1d"])
        self.assertEqual(addition.questions[3].student_answer, "100")
        self.assertEqual(addition.questions[3].individual_score, None)
        self.assertEqual(addition.questions[3].working_steps, [])
        self.assertEqual(addition.questions[3].teacher_marking.marking_type, "cross")
        self.assertEqual(result.score.obtained, 14.0)
        self.assertNotEqual(result.score.obtained, addition.section_score.obtained)

    def test_schema_invalid_json_has_specific_error(self):
        payload = {"student": {}, "sections": [{"questions": [{"student_answer": {"not": "text"}}]}], "score": {}, "teacher_comments": [], "uncertain_items": []}
        with self.assertRaises(VisionSchemaValidationError): _parse_extraction(json.dumps(payload))

    def test_incomplete_json_has_specific_truncation_error(self):
        with self.assertRaises(VisionTruncatedResponseError): _parse_extraction('{"student": {')

    def test_done_reason_length_reports_token_limit_metadata(self):
        response = Mock(status_code=200); response.raise_for_status.return_value = None
        response.json.return_value = {"response": '{"sections":', "done": True, "done_reason": "length", "eval_count": 4096}
        session = Mock(); session.post.return_value = response
        with self.assertRaises(VisionTruncatedResponseError) as caught:
            OllamaVisionService(session=session).extract(self.image)
        self.assertEqual(caught.exception.metadata["done_reason"], "length")
        self.assertEqual(caught.exception.metadata["eval_count"], 4096)
        self.assertEqual(caught.exception.metadata["configured_num_ctx"], 8192)
        self.assertTrue(caught.exception.metadata["eval_count_reached_limit"])
        self.assertTrue(caught.exception.metadata["response_ends_mid_json"])

    def test_completed_response_below_limit_is_not_truncated(self):
        payload = {"student": {}, "sections": [], "score": {}, "teacher_comments": [], "uncertain_items": []}
        response = Mock(status_code=200); response.raise_for_status.return_value = None
        response.json.return_value = {"response": json.dumps(payload), "done": True, "done_reason": "stop", "eval_count": 30}
        session = Mock(); session.post.return_value = response
        self.assertEqual(OllamaVisionService(session=session).extract(self.image).sections, [])
