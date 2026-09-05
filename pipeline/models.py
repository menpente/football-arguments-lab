"""Dataclass schemas shared by every agent in the pipeline.

These mirror the JSON shapes in the product spec (sections 5, 8, 9, 10)
so that `to_dict()` on any of them produces exactly the documented schema.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Engagement:
    likes: int = 0
    comments: int = 0
    shares: int = 0


@dataclass
class SourcePost:
    url: str
    platform: str  # "x" | "reddit" | "news" | ...
    author: str
    text: str
    engagement: Engagement = field(default_factory=Engagement)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class Candidate:
    """Section 5: candidate representation returned by the Discovery Agent."""

    id: str
    question: str
    source_posts: list[SourcePost]
    source_summary: str
    pitch: str
    better_question: str
    possible_dimensions: list[str]
    boring_risk: str
    social_signal: float
    question_quality: float
    data_feasibility: float
    story_potential: float
    surprise_potential: float
    editorial_score: float = 0.0
    # Question Refiner Agent: why better_question is sharper than `question`.
    refinement_rationale: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class GateDecision:
    """A human editor's verdict at a gate."""

    action: str  # gate 1: approve|refine|hold|reject   gate 2: approve|revise|kill
    candidate_id: Optional[str] = None
    refined_question: Optional[str] = None
    note: str = ""
    decided_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResearchBrief:
    """Section 8: Question Agent output."""

    original_claim: str
    approved_question: str
    ambiguous_terms: list[str]
    subquestions: list[str]
    metrics_needed: list[str]
    comparison_candidates: list[str]
    potential_confounders: list[str]
    strongest_possible_conclusion: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Dataset:
    """Section 9: Data Agent output. `data` holds provider-shaped payload,
    typically {"players": {name: {metric: value, ...}, ...}}.
    """

    provider: str
    competition: str
    season: str
    captured_at: str
    source_url: str
    data: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationResult:
    """Section 10: Data validation output."""

    status: str  # "passed" | "failed"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChartSpec:
    kind: str  # "bar" | "grouped_bar" | "scatter"
    title: str
    metric: str
    unit: str
    series: list[dict[str, Any]]  # [{"label": "Mbappe", "value": 24}, ...]


@dataclass
class Scene:
    """One beat of the scrollytelling narrative arc."""

    id: str
    kind: str  # hook | refine | operationalize | evidence | complication | verdict
    headline: str
    body: str
    chart: Optional[ChartSpec] = None


@dataclass
class StorySpec:
    """Section 11: Story Agent output — a narrative specification, not HTML."""

    slug: str
    title: str
    dek: str
    approved_question: str
    scenes: list[Scene]
    verdict: str
    data_sources: list[Dataset]
    editor_notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class QAReport:
    status: str  # "passed" | "failed"
    checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PublishResult:
    status: str  # "published" | "dry_run" | "blocked"
    slug: str
    output_path: str
    committed: bool = False
    commit_sha: Optional[str] = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
