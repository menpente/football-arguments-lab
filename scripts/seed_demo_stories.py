#!/usr/bin/env python3
"""Seed the published site with a few demo stories.

Runs the full pipeline non-interactively, auto-approving the top N discovered
candidates at Gate #1 and approving each finished artifact at Gate #2, then
writes them into site/ (and, with --commit, stages a git commit per story).

This is a convenience wrapper around `cli.py run` for populating the demo
site — it exercises exactly the same pipeline, gates included.

    python scripts/seed_demo_stories.py            # dry run, writes site/ only
    python scripts/seed_demo_stories.py --commit   # + one git commit per story
    python scripts/seed_demo_stories.py -n 2       # top 2 candidates instead of 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.discovery import run_discovery
from pipeline.orchestrator import ScriptedDecisions, run_pipeline
from pipeline.reasoner import HeuristicReasoner


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--count", type=int, default=3,
                        help="How many top-scored candidates to publish (default 3).")
    parser.add_argument("--commit", action="store_true",
                        help="Stage + commit each published artifact locally.")
    args = parser.parse_args()

    reasoner = HeuristicReasoner()
    candidates = run_discovery(reasoner)
    chosen = candidates[: args.count]
    if not chosen:
        print("No candidates discovered.")
        return 1

    print(f"Approving {len(chosen)} candidate(s) through both gates:")
    for c in chosen:
        print(f"  - {c.better_question}  (editorial_score={c.editorial_score})")

    scripted = ScriptedDecisions(
        gate1={c.id: {"action": "approve"} for c in chosen},
        gate2_action="approve",
    )
    result = run_pipeline(
        output_root=REPO_ROOT / "output",
        site_root=REPO_ROOT / "site",
        scripted=scripted,
        publish_commit=args.commit,
    )

    print(f"\nPipeline stage: {result['stage']}")
    for pub in result.get("published", []):
        print(f"  published: {pub['output_path']} (status={pub['status']})")
    for blocked in result.get("blocked_candidates", []):
        print(f"  blocked:   {blocked}")
    return 0 if result["stage"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
