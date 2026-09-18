import unittest
from core.models import VisionExtraction
from tools.confidence import evaluate_canonical_confidence, canonical_dual_read_agreement


def sample(answer="4", total=20):
    return VisionExtraction.model_validate({"student":{"name":"Aarav Mehta"},"sections":[{"section_name":str(s),"section_score":{"obtained":4,"maximum":4},"questions":[{"question_number":f"{s}{q}","student_answer":answer,"teacher_marking":{"marking_type":"tick"},"individual_score":{"obtained":1,"maximum":1}} for q in "abcd"]} for s in range(1,6)],"score":{"obtained":total,"maximum":20}})

class CanonicalConfidenceTests(unittest.TestCase):
    def test_identical_and_changed_evidence(self):
        first=sample(); self.assertEqual(canonical_dual_read_agreement(first, sample())[0],1)
        self.assertLess(canonical_dual_read_agreement(first, sample(answer="5"))[0], 1)
        result=evaluate_canonical_confidence(first, sample(), computed_total=20, roster=[{"id":1,"full_name":"Aarav Mehta"}])
        self.assertEqual(result["raw_confidence"],1); self.assertEqual(result["total_cross_check"],"match")
    def test_partial_and_uncertainty(self):
        first=sample(total=None); first.uncertain_items=["blurred"]
        result=evaluate_canonical_confidence(first,None,computed_total=20,roster=[])
        self.assertEqual(result["total_cross_check"],"unavailable"); self.assertIn("second_read_unavailable",result["reasons"]); self.assertGreater(result["raw_confidence"],0); self.assertLess(result["evidence_coverage"],1)

    def test_small_and_multiple_disagreements_are_proportional(self):
        first = sample(); small = sample(); small.sections[0].questions[0].student_answer = "changed"
        many = sample(); many.sections[0].questions[0].student_answer = "changed"; many.sections[1].section_score.obtained = 1; many.score.obtained = 19
        one = evaluate_canonical_confidence(first, small, computed_total=20, roster=[{"id":1,"full_name":"Aarav Mehta"}])
        several = evaluate_canonical_confidence(first, many, computed_total=20, roster=[{"id":1,"full_name":"Aarav Mehta"}])
        self.assertGreater(one["raw_confidence"], 0); self.assertGreater(one["raw_confidence"], several["raw_confidence"])
        self.assertIn("score.obtained", several["reasons"])
