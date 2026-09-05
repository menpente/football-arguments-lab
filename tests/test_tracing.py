import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline import tracing


class TestTracingDisabledByDefault(unittest.TestCase):
    def setUp(self):
        tracing._enabled = None
        self._saved = os.environ.pop("OPIK_TRACING", None)

    def tearDown(self):
        tracing._enabled = None
        if self._saved is not None:
            os.environ["OPIK_TRACING"] = self._saved

    def test_not_enabled_without_env(self):
        self.assertFalse(tracing.tracing_enabled())

    def test_traced_is_a_passthrough(self):
        calls = []

        @tracing.traced(name="adder", span_type="general")
        def add(a, b=2):
            calls.append((a, b))
            return a + b

        self.assertEqual(add(3), 5)
        self.assertEqual(add(3, b=4), 7)
        self.assertEqual(calls, [(3, 2), (3, 4)])
        self.assertEqual(add.__name__, "add")

    def test_annotate_and_flush_are_safe_noops(self):
        tracing.annotate(stage="unit-test", n=1)
        tracing.flush()

    def test_pipeline_runs_unchanged_with_tracing_off(self):
        from pipeline.discovery import run_discovery
        from pipeline.orchestrator import ScriptedDecisions, run_pipeline
        from pipeline.reasoner import HeuristicReasoner

        tmp = Path(tempfile.mkdtemp())
        try:
            top = run_discovery(HeuristicReasoner())[0]
            result = run_pipeline(
                output_root=tmp,
                scripted=ScriptedDecisions(
                    gate1={top.id: {"action": "approve"}}, gate2_action="approve"
                ),
            )
            self.assertEqual(result["stage"], "complete")
            self.assertEqual(len(result["published"]), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(importlib.util.find_spec("opik"), "opik not installed")
class TestTracingWithOpikInstalled(unittest.TestCase):
    def tearDown(self):
        tracing._enabled = None
        os.environ.pop("OPIK_TRACING", None)

    def test_enable_decision_does_not_crash(self):
        tracing._enabled = None
        os.environ["OPIK_TRACING"] = "1"
        self.assertIsInstance(tracing.tracing_enabled(), bool)


if __name__ == "__main__":
    unittest.main()
