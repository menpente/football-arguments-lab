import json
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline.discovery import run_discovery
from pipeline.orchestrator import ScriptedDecisions, run_pipeline
from pipeline.reasoner import HeuristicReasoner


class TestPipelineSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_run_publishes_an_artifact(self):
        reasoner = HeuristicReasoner()
        candidates = run_discovery(reasoner)
        self.assertGreater(len(candidates), 0)

        top = candidates[0]
        scripted = ScriptedDecisions(
            gate1={top.id: {"action": "approve"}},
            gate2_action="approve",
        )
        result = run_pipeline(output_root=self.tmp, scripted=scripted)

        self.assertEqual(result["stage"], "complete")
        self.assertEqual(len(result["published"]), 1)
        published = result["published"][0]
        artifact_path = Path(published["output_path"])
        self.assertTrue(artifact_path.exists())
        html = artifact_path.read_text()
        self.assertIn("<svg", html)
        self.assertIn(top.better_question.split()[0], html)

        run_dir = self.tmp / "runs" / published["slug"]
        for name in ("research_brief.json", "dataset.json", "validation.json",
                     "story_spec.json", "qa_report.json"):
            self.assertTrue((run_dir / name).exists(), f"missing {name}")

        site_index = (self.tmp / "index.html").read_text()
        self.assertIn(top.better_question, site_index)
        self.assertIn(f"stories/{published['slug']}/", site_index)
        manifest = json.loads((self.tmp / "manifest.json").read_text())
        self.assertEqual(manifest[0]["slug"], published["slug"])

    def test_site_root_defaults_to_output_root_when_not_given(self):
        reasoner = HeuristicReasoner()
        candidates = run_discovery(reasoner)
        top = candidates[0]
        scripted = ScriptedDecisions(
            gate1={top.id: {"action": "approve"}},
            gate2_action="approve",
        )
        result = run_pipeline(output_root=self.tmp, scripted=scripted)
        self.assertTrue((self.tmp / "index.html").exists())

    def test_separate_site_root_keeps_run_logs_and_published_site_apart(self):
        reasoner = HeuristicReasoner()
        candidates = run_discovery(reasoner)
        top = candidates[0]
        scripted = ScriptedDecisions(
            gate1={top.id: {"action": "approve"}},
            gate2_action="approve",
        )
        output_root = self.tmp / "output"
        site_root = self.tmp / "site"
        result = run_pipeline(output_root=output_root, site_root=site_root, scripted=scripted)
        self.assertEqual(result["stage"], "complete")
        self.assertTrue((output_root / "runs" / result["published"][0]["slug"]).exists())
        self.assertTrue((site_root / "index.html").exists())
        self.assertTrue((site_root / "stories" / result["published"][0]["slug"] / "index.html").exists())
        self.assertFalse((output_root / "index.html").exists())

    def test_refine_action_changes_the_question(self):
        reasoner = HeuristicReasoner()
        candidates = run_discovery(reasoner)
        top = candidates[0]
        refined_text = "Is the shot volume actually unusual for his role?"
        scripted = ScriptedDecisions(
            gate1={top.id: {"action": "refine", "refined_question": refined_text}},
            gate2_action="approve",
        )
        result = run_pipeline(output_root=self.tmp, scripted=scripted)
        self.assertEqual(result["stage"], "complete")
        slug = result["published"][0]["slug"]
        story_spec = (self.tmp / "runs" / slug / "story_spec.json").read_text()
        self.assertIn(refined_text, story_spec)

    def test_reject_action_publishes_nothing(self):
        reasoner = HeuristicReasoner()
        candidates = run_discovery(reasoner)
        scripted = ScriptedDecisions(
            gate1={c.id: {"action": "reject"} for c in candidates},
            gate2_action="approve",
        )
        result = run_pipeline(output_root=self.tmp, scripted=scripted)
        self.assertEqual(result["stage"], "stopped_no_approvals")

    def test_candidate_with_no_provider_data_is_blocked_not_a_crash(self):
        reasoner = HeuristicReasoner()
        candidates = run_discovery(reasoner)
        pedri = next(c for c in candidates if "Pedri" in c.question)
        scripted = ScriptedDecisions(
            gate1={pedri.id: {"action": "approve"}},
            gate2_action="approve",
        )
        result = run_pipeline(output_root=self.tmp, scripted=scripted)
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["published"], [])
        self.assertEqual(len(result["blocked_candidates"]), 1)
        self.assertIn("data_agent_error", result["blocked_candidates"][0])

    def test_gate2_kill_publishes_nothing(self):
        reasoner = HeuristicReasoner()
        candidates = run_discovery(reasoner)
        top = candidates[0]
        scripted = ScriptedDecisions(
            gate1={top.id: {"action": "approve"}},
            gate2_action="kill",
        )
        result = run_pipeline(output_root=self.tmp, scripted=scripted)
        self.assertEqual(result["stage"], "complete")
        self.assertEqual(result["published"], [])
        self.assertEqual(len(result["held_or_killed"]), 1)


if __name__ == "__main__":
    unittest.main()
