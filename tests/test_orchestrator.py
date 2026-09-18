import unittest
from core.orchestrator import route_confidence

def evidence(raw, coverage=1, signals=None): return {"raw_confidence":raw,"evidence_coverage":coverage,"safety_signals":signals or []}
class OrchestratorTests(unittest.TestCase):
 def test_routes_and_boundaries(self):
  self.assertEqual(route_confidence(evidence(.95))["route"],"auto_approve")
  self.assertEqual(route_confidence(evidence(.7))["route"],"grey_zone")
  self.assertEqual(route_confidence(evidence(.59))["route"],"escalate")
  self.assertEqual(route_confidence(evidence(.6))["route"],"grey_zone")
  self.assertEqual(route_confidence(evidence(.85))["route"],"auto_approve")
 def test_blockers_and_coverage(self):
  self.assertEqual(route_confidence(evidence(.99,signals=["identity_unresolved"]))["route"],"escalate")
  self.assertEqual(route_confidence(evidence(.99,coverage=.75))["route"],"grey_zone")
