import unittest

from pipeline.models import Dataset
from pipeline.validation import validate_dataset


def _dataset(players: dict) -> Dataset:
    return Dataset(
        provider="Opta Analyst",
        competition="La Liga",
        season="2026/27",
        captured_at="2026-09-05T00:00:00+00:00",
        source_url="https://example.com",
        data={"players": players},
    )


VALID_PLAYER = {
    "apps": 10,
    "minutes": 900,
    "goals": 4,
    "xg": 4.21,
    "goals_minus_xg": -0.21,
    "shots": 24,
    "shots_on_target": 14,
    "conversion": 16.67,
    "xg_per_shot": 0.18,
}


class TestValidateDataset(unittest.TestCase):
    def test_valid_dataset_passes(self):
        result = validate_dataset(_dataset({"Mbappe": VALID_PLAYER}))
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.errors, [])

    def test_goals_exceeding_shots_is_error(self):
        bad = dict(VALID_PLAYER, goals=30, shots=24)
        result = validate_dataset(_dataset({"Mbappe": bad}))
        self.assertEqual(result.status, "failed")
        self.assertTrue(any("exceed shots" in e for e in result.errors))

    def test_shots_on_target_exceeding_shots_is_error(self):
        bad = dict(VALID_PLAYER, shots_on_target=30, shots=24)
        result = validate_dataset(_dataset({"Mbappe": bad}))
        self.assertEqual(result.status, "failed")

    def test_negative_minutes_is_error(self):
        bad = dict(VALID_PLAYER, minutes=-5)
        result = validate_dataset(_dataset({"Mbappe": bad}))
        self.assertEqual(result.status, "failed")

    def test_negative_xg_is_error(self):
        bad = dict(VALID_PLAYER, xg=-1.0)
        result = validate_dataset(_dataset({"Mbappe": bad}))
        self.assertEqual(result.status, "failed")

    def test_conversion_mismatch_is_error(self):
        bad = dict(VALID_PLAYER, conversion=99.0)
        result = validate_dataset(_dataset({"Mbappe": bad}))
        self.assertEqual(result.status, "failed")
        self.assertTrue(any("conversion" in e for e in result.errors))

    def test_goals_minus_xg_mismatch_is_error(self):
        bad = dict(VALID_PLAYER, goals_minus_xg=5.0)
        result = validate_dataset(_dataset({"Mbappe": bad}))
        self.assertEqual(result.status, "failed")

    def test_small_sample_is_warning_not_error(self):
        small = dict(VALID_PLAYER, apps=3)
        result = validate_dataset(_dataset({"Mbappe": small}))
        self.assertEqual(result.status, "passed")
        self.assertTrue(any("3 league matches" in w for w in result.warnings))

    def test_empty_players_is_error(self):
        result = validate_dataset(_dataset({}))
        self.assertEqual(result.status, "failed")


if __name__ == "__main__":
    unittest.main()
