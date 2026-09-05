#!/usr/bin/env python3
"""CLI entrypoint for the Football Editorial Agent pipeline.

    python cli.py run                 # interactive: you play both human gates
    python cli.py run --auto          # scripted demo run, no prompts
    python cli.py run --auto --commit # scripted demo run + local git commit,
                                       # ready to push and deploy via GitHub Pages
    python cli.py submit "Is Rodri irreplaceable for City?"   # queue a question
    python cli.py submissions list                            # show the queue
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline.orchestrator import ScriptedDecisions, run_pipeline
from pipeline.submissions import add_submission, load_submissions

REPO_ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Football Editorial Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the full pipeline")
    run_p.add_argument("--auto", action="store_true",
                        help="Non-interactive demo run: approve the top-scored "
                             "candidate, hold the rest, approve the final artifact.")
    run_p.add_argument("--commit", action="store_true",
                        help="With --auto, also stage+commit the published artifact locally.")
    run_p.add_argument("--output", default=str(REPO_ROOT / "output"),
                        help="Output directory for ephemeral run logs (research briefs, "
                             "datasets, QA reports). Not meant to be committed.")
    run_p.add_argument("--site", default=str(REPO_ROOT / "site"),
                        help="Output directory for the published static site "
                             "(git-tracked; this is what .github/workflows/pages.yml "
                             "deploys to GitHub Pages).")

    submit_p = sub.add_parser("submit", help="Queue a reader-submitted question")
    submit_p.add_argument("question", help="The question, in quotes")
    submit_p.add_argument("--note", default="", help="Optional context for the editor")

    subs_p = sub.add_parser("submissions", help="Inspect the submission queue")
    subs_p.add_argument("action", choices=["list"], nargs="?", default="list")

    args = parser.parse_args()

    if args.command == "submit":
        s = add_submission(args.question, note=args.note)
        print(f"Queued {s.id}: {s.question}")
        print("It will appear in the Reader-submitted section of the next "
              "`cli.py run` slate.")
        return 0

    if args.command == "submissions":
        subs = load_submissions()
        new = [s for s in subs if s.status == "new"]
        if not new:
            print("No pending submissions.")
            return 0
        for s in new:
            print(f"{s.id}  {s.submitted_at[:10]}  {s.question}")
            if s.note:
                print(f"          note: {s.note}")
        return 0

    if args.command == "run":
        scripted = None
        if args.auto:
            from pipeline.discovery import run_discovery
            from pipeline.reasoner import HeuristicReasoner

            reasoner = HeuristicReasoner()
            candidates = run_discovery(reasoner)
            if not candidates:
                print("No candidates discovered.")
                return 1
            top = candidates[0]
            scripted = ScriptedDecisions(
                gate1={top.id: {"action": "approve"}},
                gate2_action="approve",
            )
            print(f"[--auto] Approving top candidate: {top.question!r} "
                  f"(editorial_score={top.editorial_score})")

        result = run_pipeline(
            output_root=Path(args.output),
            site_root=Path(args.site),
            scripted=scripted,
            publish_commit=args.commit,
        )

        log_path = Path(args.output) / "last_run.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(result, indent=2, default=str))

        print(f"\nPipeline stage: {result['stage']}")
        for pub in result.get("published", []):
            print(f"Published: {pub['output_path']} (status={pub['status']})")
        print(f"Full run log: {log_path}")
        return 0 if result["stage"] == "complete" else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
