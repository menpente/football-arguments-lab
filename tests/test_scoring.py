import unittest

from pipeline.discovery import editorial_score


class TestEditorialScore(unittest.TestCase):
    def test_matches_spec_formula(self):
        # Section 6: 0.25*social + 0.25*quality + 0.20*feasibility + 0.20*story + 0.10*surprise
        score = editorial_score(
            social_signal=9.0,
            question_quality=9.4,
            data_feasibility=9.3,
            story_potential=9.6,
            surprise_potential=9.2,
        )
        expected = 0.25 * 9.0 + 0.25 * 9.4 + 0.20 * 9.3 + 0.20 * 9.6 + 0.10 * 9.2
        self.assertAlmostEqual(score, round(expected, 2))

    def test_all_zero_is_zero(self):
        self.assertEqual(editorial_score(0, 0, 0, 0, 0), 0.0)

    def test_all_max_is_ten(self):
        self.assertEqual(editorial_score(10, 10, 10, 10, 10), 10.0)


if __name__ == "__main__":
    unittest.main()
