import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.orchestrator import ScriptedDecisions, run_pipeline
from pipeline.reasoner import HeuristicReasoner
from pipeline.submissions import add_submission, load_submissions, to_candidates


class TestSubmissionStore(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "submissions.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_appends_and_normalises(self):
        add_submission("Is Rodri irreplaceable for City", note="  from a reader ", path=self.path)
        add_submission("Does Pedri dictate games?", path=self.path)
        stored = load_submissions(self.path)
        self.assertEqual(len(stored), 2)
        self.assertEqual(stored[0].question, "Is Rodri irreplaceable for City?")
        self.assertEqual(stored[0].note, "from a reader")
        self.assertEqual(stored[0].status, "new")
        self.assertTrue(stored[0].id.startswith("sub-"))

    def test_missing_file_is_empty(self):
        self.assertEqual(load_submissions(self.tmp / "nope.json"), [])


class TestSubmissionToCandidate(unittest.TestCase):
    def setUp(self):
        self.reasoner = HeuristicReasoner()
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "submissions.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_builds_an_unscored_reader_candidate(self):
        add_submission("Is Vinicius wasteful in front of goal?", path=self.path)
        [cand] = to_candidates(load_submissions(self.path), self.reasoner)
        self.assertTrue(cand.reader_submitted)
        self.assertEqual(cand.editorial_score, 0.0)
        self.assertEqual(cand.source_posts, [])
        self.assertTrue(cand.better_question.strip())
        self.assertNotEqual(cand.better_question, cand.question)
        self.assertIn("reader_submitted", cand.to_dict())

    def test_dedup_against_published_slugs(self):
        add_submission("Does Mbappe shoot too much?", path=self.path)
        cands = to_candidates(
            load_submissions(self.path), self.reasoner,
            published_slugs={"does-mbappe-shoot-too-much"},
        )
        self.assertEqual(cands, [])

    def test_archived_submissions_are_skipped(self):
        add_submission("Does Yamal deliver end product?", path=self.path)
        subs = load_submissions(self.path)
        subs[0].status = "archived"
        self.assertEqual(to_candidates(subs, self.reasoner), [])


class TestSubmissionInPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_submitted_question_reaches_the_slate_and_publishes(self):
        path = self.tmp / "submissions.json"
        add_submission("Is Raphinha overperforming his xG?", path=path)

        result = run_pipeline(
            output_root=self.tmp,
            scripted=ScriptedDecisions(
                gate1={"": {"action": "reject"}},  # ignored keys default to hold
                gate2_action="approve",
            ),
            submissions_path=path,
        )
        slate_ids = [c["id"] for c in result["candidates"]]
        submitted = [c for c in result["candidates"] if c["reader_submitted"]]
        self.assertEqual(len(submitted), 1)
        self.assertTrue(submitted[0]["id"].startswith("sub-"))
        # it sits after the scored discovered candidates
        self.assertEqual(slate_ids[-1], submitted[0]["id"])

    def test_editor_can_approve_a_submitted_question_through_both_gates(self):
        path = self.tmp / "submissions.json"
        sub = add_submission("Is Raphinha overperforming his xG?", path=path)

        result = run_pipeline(
            output_root=self.tmp,
            scripted=ScriptedDecisions(
                gate1={sub.id: {"action": "approve"}}, gate2_action="approve"
            ),
            submissions_path=path,
        )
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(len(result["published"]), 1)


if __name__ == "__main__":
    unittest.main()
