import unittest

from pipeline.discovery import run_discovery
from pipeline.reasoner import HeuristicReasoner
from pipeline.refiner import RefinedQuestion, refine_question


class TestQuestionRefiner(unittest.TestCase):
    def setUp(self):
        self.reasoner = HeuristicReasoner()

    def _refine(self, raw: str, lead_text: str) -> RefinedQuestion:
        return refine_question(raw, lead_text, ["shot volume", "conversion"], self.reasoner)

    def test_sharper_question_differs_from_the_raw_claim(self):
        out = self._refine(
            "Does Mbappe shoot too much?",
            "Mbappe shoots too much, it's selfish, more shots than some teams.",
        )
        self.assertIsInstance(out, RefinedQuestion)
        self.assertNotEqual(out.question.strip().lower(), "does mbappe shoot too much?")
        self.assertIn("share of his team", out.question.lower())

    def test_rationale_is_present_and_substantive(self):
        out = self._refine(
            "Does Mbappe shoot too much?",
            "Mbappe shoots too much this season.",
        )
        self.assertGreaterEqual(len(out.rationale.strip()), 20)

    def test_claim_type_drives_the_rewrite(self):
        wasteful = self._refine(
            "Does Vinicius waste too many good chances?",
            "Vinicius has been wasteful in front of goal all season.",
        )
        clinical = self._refine(
            "Does Alvarez finish as clinically as the reputation says?",
            "Alvarez is the most clinical finisher in La Liga right now.",
        )
        self.assertIn("xg", wasteful.question.lower())
        self.assertNotEqual(wasteful.question, clinical.question)

    def test_unrecognised_claim_falls_back_without_crashing(self):
        out = self._refine(
            "Does Modric still have it?",
            "Modric is 40 and still starting, wild.",
        )
        self.assertTrue(out.question.strip())
        self.assertTrue(out.rationale.strip())

    def test_discovery_attaches_question_and_rationale_to_candidates(self):
        candidates = run_discovery(HeuristicReasoner())
        self.assertTrue(candidates)
        for c in candidates:
            self.assertTrue(c.better_question.strip())
            self.assertTrue(c.refinement_rationale.strip())
            self.assertNotEqual(c.better_question.strip("? ").lower(),
                                c.question.strip("? ").lower())
            self.assertIn("refinement_rationale", c.to_dict())


if __name__ == "__main__":
    unittest.main()
