"""Pluggable reasoning backend.

Every agent that needs editorial judgement (framing a pitch, decomposing a
question, writing narrative copy) calls a `Reasoner`. The default
`HeuristicReasoner` is a deterministic, offline stand-in built from simple
rules and templates, so the whole pipeline runs without any API key. Swap
in a real LLM by implementing `Reasoner` against the Claude API (see
README) and passing it to the orchestrator.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

AMBIGUOUS_TERMS = [
    "best", "overrated", "underrated", "too much", "too little",
    "better than", "worse than", "finished", "goat", "most important",
    "dominant", "efficient", "selfish", "wasteful", "carried",
    "system player", "big-game player", "best league", "best coach",
    "better midfielder", "clinical", "creative", "direct", "important",
]


class Reasoner(ABC):
    """Interface every editorial-judgement call goes through."""

    @abstractmethod
    def pitch_candidate(self, question: str, source_summary: str,
                         possible_dimensions: list[str]) -> dict:
        """Return {"pitch": str, "boring_risk": str}."""

    @abstractmethod
    def refine_question(self, raw_question: str, lead_post_text: str,
                         dimensions: list[str], suggested_question: str,
                         suggested_rationale: str) -> dict:
        """Sharpen a viral claim into a testable question for Human Gate #1.

        `suggested_*` are the deterministic seed from the claim type; return
        {"question": str, "rationale": str} — accepting or improving them.
        """

    @abstractmethod
    def decompose_question(self, approved_question: str, original_claim: str,
                            possible_dimensions: list[str],
                            comparison_candidates: list[str]) -> dict:
        """Return the non-mechanical fields of a ResearchBrief."""

    @abstractmethod
    def narrate_scene(self, kind: str, context: dict) -> dict:
        """Return {"headline": str, "body": str} for one scrollytelling scene."""


def find_ambiguous_terms(text: str) -> list[str]:
    lowered = text.lower()
    return [t for t in AMBIGUOUS_TERMS if t in lowered]


class HeuristicReasoner(Reasoner):
    """Rule-based fallback. No network calls, fully deterministic."""

    def pitch_candidate(self, question: str, source_summary: str,
                         possible_dimensions: list[str]) -> dict:
        dims = ", ".join(possible_dimensions[:3]) or "the underlying numbers"
        pitch = (
            f"A viral framing invites a verdict, but the richer story separates "
            f"{dims} instead of taking the headline claim at face value."
        )
        boring_risk = (
            "The answer may simply confirm the base rate for this role or "
            "sample size, with no real complication to report."
        )
        return {"pitch": pitch, "boring_risk": boring_risk}

    def refine_question(self, raw_question: str, lead_post_text: str,
                         dimensions: list[str], suggested_question: str,
                         suggested_rationale: str) -> dict:
        # The claim-type seed is already a sound sharper question; the
        # deterministic reasoner takes it as-is.
        return {"question": suggested_question, "rationale": suggested_rationale}

    def decompose_question(self, approved_question: str, original_claim: str,
                            possible_dimensions: list[str],
                            comparison_candidates: list[str]) -> dict:
        subquestions = [f"Is {approved_question[0].lower()}{approved_question[1:].rstrip('?')} an outlier?"]
        for dim in possible_dimensions:
            subquestions.append(f"What does the data say about {dim}?")
        if comparison_candidates:
            names = " and ".join(comparison_candidates)
            subquestions.append(f"How does this compare with {names}?")
        strongest = (
            "The volume or pattern behind the claim can be demonstrated, but "
            "a judgement about quality or intent requires evidence beyond the "
            "headline number."
        )
        return {
            "subquestions": subquestions,
            "strongest_possible_conclusion": strongest,
        }

    def narrate_scene(self, kind: str, context: dict) -> dict:
        templates = {
            "hook": (
                "{claim}",
                "Here is the claim as it travelled online: {claim}. "
                "It sounds decisive. The data says otherwise — or at least, "
                "not yet.",
            ),
            "refine": (
                "A sharper question",
                "\"{claim}\" is not testable as written. The workable version "
                "is: {question}{rationale}",
            ),
            "operationalize": (
                "What we actually measured",
                "To answer that, we tracked {metrics}.",
            ),
            "evidence": (
                "What the numbers show",
                "{evidence_summary}",
            ),
            "complication": (
                "It's not that simple",
                "{complication_summary}",
            ),
            "verdict": (
                "The strongest defensible verdict",
                "{verdict}",
            ),
        }
        headline_t, body_t = templates.get(kind, ("", "{}"))
        try:
            headline = headline_t.format(**context)
        except (KeyError, IndexError):
            headline = headline_t
        try:
            body = body_t.format(**context)
        except (KeyError, IndexError):
            body = body_t
        return {"headline": headline, "body": body}
