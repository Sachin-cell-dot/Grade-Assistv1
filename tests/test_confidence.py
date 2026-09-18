import unittest

from config import get_settings
from tools.confidence import adjust_after_confirmed_correct_escalations, clamp_auto_approve_threshold


class ConfidencePolicyTests(unittest.TestCase):
    def test_long_run_of_confirmed_correct_escalations_cannot_cross_minimum_clamp(self):
        settings = get_settings()
        threshold = adjust_after_confirmed_correct_escalations(
            current_threshold=settings.auto_approve_threshold,
            confirmed_correct_count=10_000,
            minimum=settings.threshold_min_clamp,
            maximum=settings.threshold_max_clamp,
            tighten_step=settings.recalibration_tighten_step,
        )
        self.assertEqual(threshold, settings.threshold_min_clamp)
        self.assertNotEqual(threshold, settings.escalation_floor)

    def test_adaptive_clamp_has_an_independent_upper_bound(self):
        self.assertEqual(clamp_auto_approve_threshold(1.0, 0.72, 0.95), 0.95)


if __name__ == "__main__":
    unittest.main()
