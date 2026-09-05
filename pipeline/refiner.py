"""Question Refiner Agent (feeds Human Gate #1).

A viral claim ("X shoots too much", "Y is finished") is a verdict, not a
testable question. This agent turns it into a sharper question the rest of
the pipeline can actually answer with data, plus a one-line rationale for
the editor at Gate #1.

The rewrite is delegated to the pluggable `Reasoner`: the deterministic
`HeuristicReasoner` maps the claim type to a template (below), while a real
LLM reasoner can improve on the suggestion. Either way the editor sees the
suggestion at Gate #1 and can accept it (`approve`) or override it
(`refine`).
"""
from __future__ import annotations

from dataclasses import dataclass

from .reasoner import Reasoner
from .tracing import traced


@dataclass
class RefinedQuestion:
    question: str
    rationale: str


# Everything the pipeline knows about turning a viral claim into a story
# question. Each entry:
#   (trigger keywords, viral claim verb, sharper question, rationale)
# `{player}` is filled per candidate. First match wins, so specific claims
# sit above the generic "shoots too much".
CLAIM_TYPES: list[tuple[tuple[str, ...], str, str, str]] = [
    (("wasteful", "waste"),
     "waste too many good chances",
     "Is {player} scoring fewer goals than his xG by a margin bigger than "
     "a normal cold streak?",
     "\"Wasteful\" is a feeling; the measurable version is whether his goals "
     "trail his xG by more than short-run variance explains."),
    (("finished", "washed", "done at this level"),
     "still finish at an elite level",
     "Has {player}'s conversion and xG-per-shot actually dropped from his "
     "established level, or is this just a short-sample dip?",
     "\"Finished\" needs a baseline: the sharper question compares his "
     "finishing now against his own past level rather than a vibe."),
    (("important",),
     "matter as much as the hype suggests",
     "Do {player}'s team's underlying numbers change when he is on the pitch?",
     "\"Matters as much as the hype\" is vague; the testable version asks "
     "whether the team's numbers move with him on and off the pitch."),
    (("overrated",),
     "deserve the hype",
     "Do {player}'s shot volume, xG and conversion this season match his "
     "reputation?",
     "\"Hype\" isn't measurable; the sharper question holds his actual "
     "attacking output up against the reputation."),
    (("clinical",),
     "finish as clinically as the reputation says",
     "Is {player}'s conversion rate running ahead of his xG by an amount "
     "that usually regresses?",
     "\"Clinical\" is a label; the measurable version asks whether his "
     "conversion is outrunning his xG by more than tends to last."),
    (("shoot", "shots"),
     "shoot too much",
     "Is {player} taking an unusually large share of his team's shots for "
     "his role?",
     "The claim is a verdict on style; pinning it to his share of the "
     "team's shots is something one season of data can settle."),
    (("finish", "hot"),
     "finish better than expected, or just run hot",
     "Is {player}'s goals-minus-xG gap big enough to be a real finishing "
     "edge rather than variance?",
     "\"Runs hot\" vs. \"good finisher\" is the whole question; the "
     "testable version asks whether the gap is beyond noise."),
]

DEFAULT_CLAIM: tuple[str, str, str] = (
    "live up to the claim",
    "Which specific, measurable version of \"{claim}\" does the data support?",
    "The claim is a broad verdict; the refiner asks which concrete, "
    "measurable version of it the available data can actually address.",
)


def _player_of(raw_question: str) -> str:
    parts = raw_question.split()
    return parts[1] if len(parts) > 1 else "the player"


def _match(lead_post_text: str) -> tuple[str, str, str]:
    """(viral claim verb, sharper question template, rationale) for a post."""
    lowered = lead_post_text.lower()
    for keywords, claim_verb, question_tpl, rationale in CLAIM_TYPES:
        if any(k in lowered for k in keywords):
            return claim_verb, question_tpl, rationale
    return DEFAULT_CLAIM


def viral_question(player: str, lead_post_text: str) -> str:
    """The claim as it travelled online, e.g. 'Does Mbappe shoot too much?'."""
    claim_verb, _, _ = _match(lead_post_text)
    return f"Does {player} {claim_verb}?"


def _suggest(raw_question: str, lead_post_text: str) -> tuple[str, str]:
    """Heuristic seed: (sharper question, rationale) from the claim type."""
    player = _player_of(raw_question)
    _, question_tpl, rationale = _match(lead_post_text)
    return (
        question_tpl.format(player=player, claim=raw_question.rstrip("?")),
        rationale,
    )


@traced(name="question_refiner")
def refine_question(raw_question: str, lead_post_text: str,
                    dimensions: list[str], reasoner: Reasoner) -> RefinedQuestion:
    suggested_question, suggested_rationale = _suggest(raw_question, lead_post_text)
    result = reasoner.refine_question(
        raw_question=raw_question,
        lead_post_text=lead_post_text,
        dimensions=dimensions,
        suggested_question=suggested_question,
        suggested_rationale=suggested_rationale,
    )
    return RefinedQuestion(
        question=result.get("question") or suggested_question,
        rationale=result.get("rationale") or suggested_rationale,
    )
