"""Section 8: Question Agent.

Turns an editor-approved question into a testable research brief.
"""
from __future__ import annotations

from .discovery import KNOWN_PLAYERS
from .models import Candidate, ResearchBrief
from .reasoner import Reasoner, find_ambiguous_terms
from .tracing import traced

BASE_METRICS = {
    "shot volume": ["shots"],
    "conversion": ["goals", "shots", "conversion"],
    "xg": ["xg"],
    "xG": ["xg"],
    "xg per shot": ["xg_per_shot"],
    "team shot share": ["shots"],
    "passes per 90": ["passes"],
    "progressive passes": ["passes"],
    "minutes played": ["minutes"],
    "team dependency": ["minutes", "apps"],
}

STANDARD_CONFOUNDERS = ["penalties", "position", "minutes played", "small sample size"]


@traced(name="question_agent")
def build_research_brief(approved_question: str, candidate: Candidate,
                          reasoner: Reasoner) -> ResearchBrief:
    ambiguous_terms = find_ambiguous_terms(approved_question) or find_ambiguous_terms(candidate.question)

    metrics: list[str] = []
    for dim in candidate.possible_dimensions:
        for metric in BASE_METRICS.get(dim.lower(), [dim]):
            if metric not in metrics:
                metrics.append(metric)
    if "shots on target" not in metrics and "shots" in metrics:
        metrics.append("shots on target")

    comparison_candidates = _infer_comparisons(candidate)

    # Carry the refiner's rationale only if the editor accepted its suggestion;
    # if they typed their own refined question, the rationale no longer fits.
    accepted_suggestion = approved_question.strip() == candidate.better_question.strip()
    refinement_rationale = candidate.refinement_rationale if accepted_suggestion else ""

    reasoned = reasoner.decompose_question(
        approved_question=approved_question,
        original_claim=candidate.question,
        possible_dimensions=candidate.possible_dimensions,
        comparison_candidates=comparison_candidates,
    )

    return ResearchBrief(
        original_claim=candidate.question,
        approved_question=approved_question,
        ambiguous_terms=ambiguous_terms,
        subquestions=reasoned["subquestions"],
        metrics_needed=metrics,
        comparison_candidates=comparison_candidates,
        potential_confounders=STANDARD_CONFOUNDERS,
        strongest_possible_conclusion=reasoned["strongest_possible_conclusion"],
        refinement_rationale=refinement_rationale,
    )


def _infer_comparisons(candidate: Candidate) -> list[str]:
    """Any other known player named in the same source posts becomes a
    natural comparison point (mirrors the Mbappe -> Raphinha example)."""
    subject = candidate.question.split()[1] if len(candidate.question.split()) > 1 else ""
    mentioned: list[str] = []
    for post in candidate.source_posts:
        for player in KNOWN_PLAYERS:
            if player != subject and player.lower() in post.text.lower() and player not in mentioned:
                mentioned.append(player)
    return mentioned[:2]
