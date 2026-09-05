"""Section 11: Story Agent.

Builds a narrative specification (not HTML) that walks the editorial arc
from section 2: claim -> ambiguity -> refined question -> operationalized
metrics -> evidence -> complication -> strongest defensible verdict.
"""
from __future__ import annotations

import re

from .models import ChartSpec, Dataset, ResearchBrief, Scene, StorySpec
from .reasoner import Reasoner
from .tracing import traced


def _slugify(text: str) -> str:
    text = text.lower().replace("'", "")
    words = re.sub(r"[^a-z0-9]+", "-", text).strip("-").split("-")
    slug = ""
    for word in words:
        if slug and len(slug) + 1 + len(word) > 60:
            break
        slug = f"{slug}-{word}" if slug else word
    return slug or "story"


def _metric_chart(dataset: Dataset, metric: str, title: str, unit: str) -> ChartSpec | None:
    players = dataset.data.get("players", {})
    series = [
        {"label": name, "value": stats[metric]}
        for name, stats in players.items()
        if metric in stats
    ]
    if not series:
        return None
    return ChartSpec(kind="bar", title=title, metric=metric, unit=unit, series=series)


def _evidence_summary(dataset: Dataset, subject: str, comparisons: list[str]) -> str:
    players = dataset.data.get("players", {})
    lines = []
    for name in [subject, *comparisons]:
        stats = players.get(name)
        if not stats:
            continue
        lines.append(
            f"{name}: {stats['shots']} shots, {stats['goals']} goals "
            f"({stats['conversion']}% conversion), {stats['xg']} xG, "
            f"{stats['xg_per_shot']} xG/shot."
        )
    return " ".join(lines)


def _complication_summary(dataset: Dataset, subject: str, comparisons: list[str]) -> str:
    players = dataset.data.get("players", {})
    subj = players.get(subject, {})
    notes = []
    subj_gmx = subj.get("goals_minus_xg")
    if subj_gmx is not None:
        if subj_gmx < 0:
            notes.append(
                f"{subject} is scoring below their xG ({subj_gmx:+.2f}), which "
                f"looks like underperformance more than bad shot selection."
            )
        elif subj_gmx > 0:
            notes.append(f"{subject} is outscoring their xG ({subj_gmx:+.2f}).")
    for name in comparisons:
        stats = players.get(name)
        if not stats:
            continue
        gmx = stats.get("goals_minus_xg")
        if gmx is not None and gmx > 0.5:
            notes.append(
                f"{name}'s {gmx:+.2f} goals-vs-xG gap is hard to sustain over a "
                f"full season — some regression is likely before a verdict on "
                f"'better finisher' should be trusted."
            )
    return " ".join(notes) or "The sample is still too small to rule out variance."


@traced(name="story_agent")
def build_story_spec(brief: ResearchBrief, dataset: Dataset, subject: str,
                      reasoner: Reasoner) -> StorySpec:
    comparisons = brief.comparison_candidates
    slug = _slugify(brief.original_claim)

    scenes: list[Scene] = []

    hook = reasoner.narrate_scene("hook", {"claim": brief.original_claim})
    scenes.append(Scene(id="hook", kind="hook", headline=hook["headline"], body=hook["body"]))

    rationale_clause = (
        f" {brief.refinement_rationale}" if brief.refinement_rationale else ""
    )
    refine = reasoner.narrate_scene(
        "refine", {"claim": brief.original_claim, "question": brief.approved_question,
                   "rationale": rationale_clause}
    )
    scenes.append(Scene(id="refine", kind="refine", headline=refine["headline"], body=refine["body"]))

    operationalize = reasoner.narrate_scene(
        "operationalize", {"metrics": ", ".join(brief.metrics_needed)}
    )
    scenes.append(
        Scene(id="operationalize", kind="operationalize",
              headline=operationalize["headline"], body=operationalize["body"])
    )

    evidence_summary = _evidence_summary(dataset, subject, comparisons)
    evidence = reasoner.narrate_scene("evidence", {"evidence_summary": evidence_summary})
    scenes.append(
        Scene(id="evidence", kind="evidence", headline=evidence["headline"],
              body=evidence["body"],
              chart=_metric_chart(dataset, "shots", "Shots this season", "shots"))
    )
    scenes.append(
        Scene(id="evidence-efficiency", kind="evidence", headline="Volume vs. efficiency",
              body="Raw shot totals and conversion rate side by side.",
              chart=_metric_chart(dataset, "conversion", "Conversion rate", "%"))
    )
    scenes.append(
        Scene(id="evidence-xg", kind="evidence", headline="Shot quality",
              body="xG per shot approximates how good the chances actually were.",
              chart=_metric_chart(dataset, "xg_per_shot", "xG per shot", "xG"))
    )

    complication_summary = _complication_summary(dataset, subject, comparisons)
    complication = reasoner.narrate_scene("complication", {"complication_summary": complication_summary})
    scenes.append(
        Scene(id="complication", kind="complication", headline=complication["headline"],
              body=complication["body"])
    )

    verdict = reasoner.narrate_scene(
        "verdict", {"verdict": brief.strongest_possible_conclusion}
    )
    scenes.append(Scene(id="verdict", kind="verdict", headline=verdict["headline"], body=verdict["body"]))

    # The headline is the viral claim (the hook); the dek is the sharper,
    # testable question the story actually answers.
    title = brief.original_claim
    dek = brief.approved_question

    return StorySpec(
        slug=slug,
        title=title,
        dek=dek,
        approved_question=brief.approved_question,
        scenes=scenes,
        verdict=brief.strongest_possible_conclusion,
        data_sources=[dataset],
    )
