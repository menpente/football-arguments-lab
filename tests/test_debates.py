import json
import tempfile
import unittest
from pathlib import Path

from pipeline.debates import (
    DEFAULT_SRC,
    Debate,
    load_debates,
    publish_debates,
    validate_debates,
)


def _debate(**overrides) -> Debate:
    base = dict(
        id="messi-ronaldo",
        tag="GOAT debate",
        title="Messi vs Ronaldo",
        q="Who is the best player in the world?",
        a="Lionel Messi",
        b="Cristiano Ronaldo",
        teaser="Scoring, creation and longevity pull the answer in different directions.",
        criteria=[
            ["scoring", "Scoring", 80, [96, 100]],
            ["creation", "Creation", 70, [100, 82]],
            ["longevity", "Longevity", 50, [88, 100]],
        ],
        scenes=[
            ["Start with totals", "Ronaldo leads the raw goal total.", "Career goals", 927, 978, "club + country", "A total is rate x opportunity."],
            ["Change the denominator", "Messi scores more often per game.", "Goals per game", 0.79, 0.73, "career", "Volume vs efficiency flips it."],
            ["Add creation", "Messi has more goal contributions.", "Goal contributions", 1348, 1239, "goals + assists", "Finishing and creating differ."],
        ],
        sources=[["FBref", "https://fbref.com/"]],
    )
    base.update(overrides)
    return Debate(**base)


class TestValidateDebates(unittest.TestCase):
    def test_a_well_formed_debate_has_no_errors(self):
        self.assertEqual(validate_debates([_debate()]), [])

    def test_duplicate_id_is_an_error(self):
        errs = validate_debates([_debate(), _debate()])
        self.assertTrue(any("duplicate id" in e for e in errs))

    def test_bad_id_characters_are_an_error(self):
        errs = validate_debates([_debate(id="Messi Ronaldo!")])
        self.assertTrue(any("id must match" in e for e in errs))

    def test_empty_title_is_an_error(self):
        errs = validate_debates([_debate(title="  ")])
        self.assertTrue(any("title is empty" in e for e in errs))

    def test_identical_sides_are_an_error(self):
        errs = validate_debates([_debate(a="Messi", b="Messi")])
        self.assertTrue(any("a and b are identical" in e for e in errs))

    def test_too_few_and_too_many_criteria_are_errors(self):
        two = _debate(criteria=_debate().criteria[:2])
        six = _debate(criteria=_debate().criteria + _debate().criteria)
        self.assertTrue(any("3-5 criteria" in e for e in validate_debates([two])))
        self.assertTrue(any("3-5 criteria" in e for e in validate_debates([six])))

    def test_criterion_weight_out_of_range_is_an_error(self):
        d = _debate()
        d.criteria[0][2] = 150
        self.assertTrue(any("weight must be an int in 0..100" in e for e in validate_debates([d])))

    def test_criterion_score_out_of_range_is_an_error(self):
        d = _debate()
        d.criteria[0][3] = [-5, 100]
        self.assertTrue(any("scores must be two numbers in 0..100" in e for e in validate_debates([d])))

    def test_duplicate_criterion_key_is_an_error(self):
        d = _debate()
        d.criteria[1][0] = d.criteria[0][0]
        self.assertTrue(any("duplicate key" in e for e in validate_debates([d])))

    def test_scene_with_wrong_field_count_is_an_error(self):
        d = _debate()
        d.scenes[0] = d.scenes[0][:6]
        self.assertTrue(any("7 fields" in e for e in validate_debates([d])))

    def test_scene_with_non_numeric_value_is_an_error(self):
        d = _debate()
        d.scenes[0][3] = "lots"
        self.assertTrue(any("must be a number" in e for e in validate_debates([d])))

    def test_source_url_without_scheme_is_an_error(self):
        errs = validate_debates([_debate(sources=[["FBref", "fbref.com"]])])
        self.assertTrue(any("http" in e for e in errs))

    def test_empty_sources_is_an_error(self):
        errs = validate_debates([_debate(sources=[])])
        self.assertTrue(any("at least one source" in e for e in errs))


class TestLoadDebates(unittest.TestCase):
    def test_round_trips_a_json_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "debates.json"
            p.write_text(json.dumps([_debate().to_dict()]))
            loaded = load_debates(p)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].id, "messi-ronaldo")
            self.assertEqual(validate_debates(loaded), [])


class TestSeedFile(unittest.TestCase):
    def test_committed_debates_json_is_valid(self):
        debates = load_debates(DEFAULT_SRC)
        self.assertGreaterEqual(len(debates), 3)
        self.assertEqual(validate_debates(debates), [])

    def test_seed_includes_the_yamal_messi_debate(self):
        ids = {d.id for d in load_debates(DEFAULT_SRC)}
        self.assertIn("yamal-teenage-messi", ids)


class TestPublishDebates(unittest.TestCase):
    def test_publish_rejects_invalid_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "bad.json"
            src.write_text(json.dumps([_debate(id="Bad Id").to_dict()]))
            with self.assertRaises(ValueError):
                publish_debates(src, Path(tmp))


if __name__ == "__main__":
    unittest.main()
