"""Wires the ten pipeline stages together (spec section 1/3), pausing at
Human Gate #1 and Human Gate #2. Runs interactively by default; pass
`scripted_decisions` to drive it non-interactively (demos, tests, CI).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from . import gates, submissions
from .artifact_agent import write_artifact
from .data_agent import ProviderConnector, fetch_dataset
from .discovery import SourceConnector, run_discovery
from .models import Candidate, GateDecision
from .publish_agent import publish
from .qa_agent import run_qa
from .question_agent import build_research_brief
from .reasoner import HeuristicReasoner, Reasoner
from .story_agent import build_story_spec
from .tracing import annotate, flush, traced
from .validation import validate_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent


class ScriptedDecisions:
    """Non-interactive inputs for both human gates, used by demos/tests."""

    def __init__(self, gate1: dict[str, dict], gate2_action: str = "approve", gate2_note: str = ""):
        self.gate1 = gate1  # candidate_id -> {"action": ..., "refined_question": ...}
        self.gate2_action = gate2_action
        self.gate2_note = gate2_note


def _dump(obj, path: Path) -> None:
    path.write_text(json.dumps(obj.to_dict() if hasattr(obj, "to_dict") else obj, indent=2, default=str))


def _published_slugs(site_root: Path) -> set[str]:
    manifest = site_root / "manifest.json"
    if not manifest.exists():
        return set()
    try:
        return {entry["slug"] for entry in json.loads(manifest.read_text())}
    except (ValueError, KeyError):
        return set()


@traced(name="pipeline_run")
def run_pipeline(
    reasoner: Optional[Reasoner] = None,
    connectors: Optional[list[SourceConnector]] = None,
    provider_connector: Optional[ProviderConnector] = None,
    output_root: Optional[Path] = None,
    site_root: Optional[Path] = None,
    scripted: Optional[ScriptedDecisions] = None,
    publish_commit: bool = False,
    submissions_path: Optional[Path] = None,
) -> dict:
    run_log = _run_pipeline(
        reasoner, connectors, provider_connector, output_root,
        site_root, scripted, publish_commit, submissions_path,
    )
    annotate(
        outcome_stage=run_log.get("stage"),
        published=len(run_log.get("published") or []),
        blocked=len(run_log.get("blocked_candidates") or []),
        held_or_killed=len(run_log.get("held_or_killed") or []),
    )
    flush()
    return run_log


def _run_pipeline(
    reasoner: Optional[Reasoner],
    connectors: Optional[list[SourceConnector]],
    provider_connector: Optional[ProviderConnector],
    output_root: Optional[Path],
    site_root: Optional[Path],
    scripted: Optional[ScriptedDecisions],
    publish_commit: bool,
    submissions_path: Optional[Path],
) -> dict:
    reasoner = reasoner or HeuristicReasoner()
    output_root = output_root or (REPO_ROOT / "output")
    site_root = site_root or output_root
    run_log: dict = {"stage": "discovery"}

    # 1-2. Discovery + Candidate Scoring
    candidates = run_discovery(reasoner, connectors=connectors)

    # Reader-submitted questions join the slate below the scored ones, unscored.
    published_slugs = _published_slugs(site_root)
    submitted = submissions.to_candidates(
        submissions.load_submissions(submissions_path), reasoner, published_slugs
    )
    candidates = candidates + submitted

    run_log["candidates"] = [c.to_dict() for c in candidates]
    if not candidates:
        run_log["stage"] = "stopped_no_candidates"
        return run_log

    # ==== HUMAN GATE #1 ====
    if scripted is not None:
        decisions = gates.run_gate1_scripted(candidates, scripted.gate1)
    else:
        decisions = gates.run_gate1_interactive(candidates)
    run_log["gate1_decisions"] = [d.to_dict() for d in decisions]
    annotate(gate1_decisions={d.candidate_id: d.action for d in decisions})

    approved: list[tuple[Candidate, GateDecision]] = [
        (c, d) for c, d in zip(candidates, decisions) if d.action in ("approve", "refine")
    ]
    if not approved:
        run_log["stage"] = "stopped_no_approvals"
        return run_log

    stories_published = []
    for candidate, decision in approved:
        approved_question = gates.approved_question_for(candidate, decision)
        subject = candidate.question.split()[1] if len(candidate.question.split()) > 1 else ""

        # 3. Question Agent
        brief = build_research_brief(approved_question, candidate, reasoner)

        # 4. Research/Data Agent
        try:
            dataset = fetch_dataset(brief, subject, connector=provider_connector)
        except LookupError as exc:
            run_log.setdefault("blocked_candidates", []).append(
                {"candidate_id": candidate.id, "data_agent_error": str(exc)}
            )
            continue

        # Data validation (blocks on error)
        validation = validate_dataset(dataset)
        if validation.errors:
            run_log.setdefault("blocked_candidates", []).append(
                {"candidate_id": candidate.id, "validation": validation.to_dict()}
            )
            continue

        # 5. Story Agent
        story = build_story_spec(brief, dataset, subject, reasoner)

        # 6. Artifact Agent
        run_dir = output_root / "runs" / story.slug
        artifact_path = write_artifact(story, run_dir)

        # 7. QA Agent
        qa = run_qa(story, validation)
        if qa.status != "passed":
            run_log.setdefault("blocked_candidates", []).append(
                {"candidate_id": candidate.id, "qa": qa.to_dict()}
            )
            continue

        # ==== HUMAN GATE #2 ====
        if scripted is not None:
            gate2 = gates.run_gate2_scripted(scripted.gate2_action, scripted.gate2_note)
        else:
            gate2 = gates.run_gate2_interactive(story.slug)

        annotate(gate2=f"{story.slug}:{gate2.action}")
        if gate2.action != "approve":
            run_log.setdefault("held_or_killed", []).append(
                {"slug": story.slug, "decision": gate2.to_dict()}
            )
            continue

        # 8. Publish Agent
        result = publish(story, artifact_path, site_root, git_commit=publish_commit)
        stories_published.append(result.to_dict())

        _dump(brief, run_dir / "research_brief.json")
        _dump(dataset, run_dir / "dataset.json")
        _dump(validation, run_dir / "validation.json")
        _dump(story, run_dir / "story_spec.json")
        _dump(qa, run_dir / "qa_report.json")

    run_log["stage"] = "complete"
    run_log["published"] = stories_published
    return run_log
