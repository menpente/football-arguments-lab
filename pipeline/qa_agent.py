"""Section 13 (QA Agent): automated checks that run before Human Gate #2.

QA does not re-judge editorial quality (that's the human's job at the
gate) — it verifies the artifact is structurally sound: every required
narrative beat is present, charts have data, the underlying dataset passed
validation, and nothing reads as an empty placeholder.
"""
from __future__ import annotations

from .models import QAReport, StorySpec, ValidationResult
from .tracing import traced

REQUIRED_SCENE_KINDS = {"hook", "refine", "operationalize", "evidence", "complication", "verdict"}
MIN_HEADLINE_LEN = 3
MIN_BODY_LEN = 20


@traced(name="qa_agent")
def run_qa(story: StorySpec, validation: ValidationResult) -> QAReport:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = list(validation.warnings)

    if validation.errors:
        errors.extend(f"upstream data validation: {e}" for e in validation.errors)
    checks.append({"name": "data_validation_passed", "passed": not validation.errors})

    present_kinds = {s.kind for s in story.scenes}
    missing_kinds = REQUIRED_SCENE_KINDS - present_kinds
    if missing_kinds:
        errors.append(f"Story is missing narrative beats: {', '.join(sorted(missing_kinds))}")
    checks.append({"name": "narrative_arc_complete", "passed": not missing_kinds})

    empty_scenes = [
        s.id for s in story.scenes
        if len(s.headline.strip()) < MIN_HEADLINE_LEN or len(s.body.strip()) < MIN_BODY_LEN
    ]
    if empty_scenes:
        errors.append(f"Scenes with placeholder-thin content: {', '.join(empty_scenes)}")
    checks.append({"name": "no_placeholder_scenes", "passed": not empty_scenes})

    evidence_scenes = [s for s in story.scenes if s.kind == "evidence"]
    charts_present = any(s.chart is not None for s in evidence_scenes)
    if not charts_present:
        errors.append("No evidence scene carries a chart.")
    checks.append({"name": "evidence_has_charts", "passed": charts_present})

    if not story.verdict.strip():
        errors.append("Story has no verdict text.")
    checks.append({"name": "verdict_present", "passed": bool(story.verdict.strip())})

    if not story.data_sources:
        errors.append("Story cites no data sources.")
    checks.append({"name": "sources_cited", "passed": bool(story.data_sources)})

    status = "failed" if errors else "passed"
    return QAReport(status=status, checks=checks, warnings=warnings, errors=errors)
