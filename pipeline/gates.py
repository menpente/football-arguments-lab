"""Human Gate #1 and #2 (sections 7 and Gate #2 after QA).

The workflow must stop after producing the slate/artifact until a human
decision exists. This module implements that pause as a CLI prompt, with a
non-interactive path (a decisions dict) so the pipeline can be scripted or
tested without a human at the keyboard.
"""
from __future__ import annotations

from .models import Candidate, GateDecision

GATE1_ACTIONS = {"approve", "refine", "hold", "reject"}
GATE2_ACTIONS = {"approve", "revise", "kill"}


def print_slate(candidates: list[Candidate]) -> None:
    print("\n=== Editorial slate (Human Gate #1) ===")
    for i, c in enumerate(candidates, 1):
        print(f"\n[{i}] {c.question}  (editorial_score={c.editorial_score})")
        print(f"    Source: {c.source_summary}")
        print(f"    Why now / pitch: {c.pitch}")
        print(f"    Suggested refined question: {c.better_question}")
        print(f"    Likely metrics: {', '.join(c.possible_dimensions)}")
        print(f"    Data feasibility: {c.data_feasibility}/10")
        print(f"    What could make it boring: {c.boring_risk}")


def run_gate1_interactive(candidates: list[Candidate]) -> list[GateDecision]:
    print_slate(candidates)
    decisions = []
    for c in candidates:
        while True:
            raw = input(
                f"\nDecision for '{c.question}' [approve/refine/hold/reject]: "
            ).strip().lower()
            if raw in GATE1_ACTIONS:
                break
            print(f"Please enter one of {sorted(GATE1_ACTIONS)}.")
        refined = None
        if raw == "refine":
            refined = input("Refined question: ").strip()
        decisions.append(GateDecision(action=raw, candidate_id=c.id, refined_question=refined))
    return decisions


def run_gate1_scripted(candidates: list[Candidate], decisions_by_id: dict[str, dict]) -> list[GateDecision]:
    """Non-interactive Gate #1, e.g. for automated demo runs or tests.

    `decisions_by_id` maps candidate.id -> {"action": ..., "refined_question": ...}.
    Candidates with no entry default to "hold".
    """
    decisions = []
    for c in candidates:
        entry = decisions_by_id.get(c.id, {"action": "hold"})
        action = entry["action"]
        if action not in GATE1_ACTIONS:
            raise ValueError(f"Invalid gate 1 action: {action}")
        decisions.append(
            GateDecision(
                action=action,
                candidate_id=c.id,
                refined_question=entry.get("refined_question"),
            )
        )
    return decisions


def approved_question_for(candidate: Candidate, decision: GateDecision) -> str:
    if decision.action == "refine" and decision.refined_question:
        return decision.refined_question
    return candidate.better_question


def run_gate2_interactive(slug: str) -> GateDecision:
    print(f"\n=== Final review (Human Gate #2): {slug} ===")
    while True:
        raw = input("Decision [approve/revise/kill]: ").strip().lower()
        if raw in GATE2_ACTIONS:
            break
        print(f"Please enter one of {sorted(GATE2_ACTIONS)}.")
    note = ""
    if raw != "approve":
        note = input("Note for the team: ").strip()
    return GateDecision(action=raw, note=note)


def run_gate2_scripted(action: str, note: str = "") -> GateDecision:
    if action not in GATE2_ACTIONS:
        raise ValueError(f"Invalid gate 2 action: {action}")
    return GateDecision(action=action, note=note)
