"""Section 4-6: Discovery Agent + Candidate Scoring.

Finds candidate posts, clusters them into editorial themes, and turns each
cluster into a scored `Candidate`. Source connectors are pluggable so real
X/Reddit/news APIs can replace the bundled JSON fixtures without touching
the clustering or scoring logic.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path

from .models import Candidate, Engagement, SourcePost
from .reasoner import Reasoner, find_ambiguous_terms

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

THEME_KEYWORDS = [
    "best", "overrated", "underrated", "too much", "too little",
    "better than", "worse than", "finished", "goat", "most important",
    "dominant", "efficient", "selfish", "wasteful", "carried",
    "system player", "big-game player", "best league", "best coach",
    "better midfielder",
]

NUMERIC_HOOK = re.compile(r"\d")

# crude entity list for the MVP clusterer; a real system would use NER.
KNOWN_PLAYERS = ["Mbappe", "Raphinha", "Lewandowski", "Vinicius", "Yamal", "Alvarez", "Pedri"]


class SourceConnector(ABC):
    """One social/news source. Implementations return raw `SourcePost`s."""

    platform: str

    @abstractmethod
    def fetch_posts(self) -> list[SourcePost]:
        ...


class JsonFixtureConnector(SourceConnector):
    """Reads a bundled JSON fixture, standing in for a live API call.

    Swap for a real connector (tweepy for X, praw for Reddit, a news search
    API) by implementing `fetch_posts` the same way and keeping this
    contract — clustering/scoring code never needs to change.
    """

    def __init__(self, platform: str, fixture_path: Path):
        self.platform = platform
        self.fixture_path = fixture_path

    def fetch_posts(self) -> list[SourcePost]:
        raw = json.loads(self.fixture_path.read_text())
        posts = []
        for item in raw:
            posts.append(
                SourcePost(
                    url=item["url"],
                    platform=item["platform"],
                    author=item["author"],
                    text=item["text"],
                    engagement=Engagement(**item["engagement"]),
                )
            )
        return posts


def default_connectors() -> list[SourceConnector]:
    fixture = DATA_DIR / "sources" / "sample_posts.json"
    return [JsonFixtureConnector("mixed", fixture)]


def _mentions_player(text: str) -> str | None:
    for player in KNOWN_PLAYERS:
        if player.lower() in text.lower():
            return player
    return None


def _has_numeric_hook(text: str) -> bool:
    return bool(NUMERIC_HOOK.search(text))


def cluster_posts(posts: list[SourcePost]) -> dict[str, list[SourcePost]]:
    """Group posts by the player they debate. A post qualifies if it carries
    a theme keyword OR a numerical hook (section 4 treats both as signals of
    a good candidate); posts naming no known player are dropped.
    """
    clusters: dict[str, list[SourcePost]] = {}
    for post in posts:
        lowered = post.text.lower()
        has_theme = any(k in lowered for k in THEME_KEYWORDS)
        player = _mentions_player(post.text)
        if not player or not (has_theme or _has_numeric_hook(post.text)):
            continue
        clusters.setdefault(player, []).append(post)
    return clusters


def _social_signal(posts: list[SourcePost]) -> float:
    total = sum(p.engagement.likes + p.engagement.comments * 3 + p.engagement.shares * 2 for p in posts)
    # log-ish squash into 0-10 without pulling in numpy/math surprises
    score = min(10.0, 2.0 + (total ** 0.35) / 6.0)
    return round(score, 1)


def _question_quality(question: str) -> float:
    terms = find_ambiguous_terms(question)
    base = 6.0 + min(len(terms), 3) * 1.1
    return round(min(base, 10.0), 1)


def _data_feasibility(possible_dimensions: list[str]) -> float:
    known_metrics = {"shots", "goals", "xg", "xg per shot", "conversion", "team shot share",
                      "passes", "shot volume"}
    covered = sum(1 for d in possible_dimensions if d.lower() in known_metrics)
    base = 5.0 + covered * 1.2
    return round(min(base, 10.0), 1)


def _story_potential(posts: list[SourcePost], has_numeric_hook: bool) -> float:
    base = 7.0 if has_numeric_hook else 5.5
    base += min(len(posts) - 1, 2) * 0.5
    return round(min(base, 10.0), 1)


def _surprise_potential(question: str) -> float:
    # binary framings ("too much", "overrated") promise a reversal-friendly story
    reversal_terms = ["too much", "too little", "overrated", "underrated", "wasteful", "selfish"]
    lowered = question.lower()
    base = 8.5 if any(t in lowered for t in reversal_terms) else 6.5
    return round(base, 1)


def editorial_score(social_signal: float, question_quality: float,
                     data_feasibility: float, story_potential: float,
                     surprise_potential: float) -> float:
    score = (
        0.25 * social_signal
        + 0.25 * question_quality
        + 0.20 * data_feasibility
        + 0.20 * story_potential
        + 0.10 * surprise_potential
    )
    return round(score, 2)


DIMENSION_LIBRARY = {
    "Mbappe": ["shot volume", "conversion", "xG", "xG per shot", "team shot share"],
    "Raphinha": ["conversion", "xG", "xG per shot", "shot volume"],
    "Lewandowski": ["conversion", "xG", "xG per shot", "shot volume"],
    "Vinicius": ["shot volume", "conversion", "xG", "xG per shot"],
    "Yamal": ["shot volume", "conversion", "xG", "xG per shot"],
    "Alvarez": ["conversion", "xG", "xG per shot", "shot volume"],
    "Pedri": ["passes per 90", "progressive passes", "minutes played", "team dependency"],
}


def build_candidate(player: str, posts: list[SourcePost], reasoner: Reasoner) -> Candidate:
    lead_post = max(posts, key=lambda p: p.engagement.likes)
    claim_verb, sharper_template = _infer_claim(lead_post.text)
    question = f"Does {player} {claim_verb}?"
    # The viral claim is a vague verdict; the sharper question is the specific,
    # measurable thing the story will actually test. A real LLM reasoner can
    # improve on this; the heuristic seed comes from the claim type.
    sharper_question = sharper_template.format(player=player)
    dims = DIMENSION_LIBRARY.get(player, ["shot volume", "conversion"])
    pitch_fields = reasoner.pitch_candidate(question, lead_post.text, dims)

    has_hook = any(_has_numeric_hook(p.text) for p in posts)
    social = _social_signal(posts)
    quality = _question_quality(question)
    feasibility = _data_feasibility(dims)
    story = _story_potential(posts, has_hook)
    surprise = _surprise_potential(question)

    candidate = Candidate(
        id=f"{player.lower()}-{_slugify(question)}",
        question=question,
        source_posts=posts,
        source_summary=f"Viral debate about {player} clustered from {len(posts)} posts.",
        pitch=pitch_fields["pitch"],
        better_question=sharper_question or pitch_fields["better_question"],
        possible_dimensions=dims,
        boring_risk=pitch_fields["boring_risk"],
        social_signal=social,
        question_quality=quality,
        data_feasibility=feasibility,
        story_potential=story,
        surprise_potential=surprise,
    )
    candidate.editorial_score = editorial_score(social, quality, feasibility, story, surprise)
    return candidate


# Each entry: (trigger keywords, the vague viral claim, the sharper testable
# question). `{player}` is filled in per candidate. Order matters — the first
# match wins, so specific claims sit above the generic "shoots too much".
CLAIM_TYPES: list[tuple[tuple[str, ...], str, str]] = [
    (("wasteful", "waste"),
     "waste too many good chances",
     "Is {player} scoring fewer goals than his xG by a margin bigger than "
     "a normal cold streak?"),
    (("finished", "washed", "done at this level"),
     "still finish at an elite level",
     "Has {player}'s conversion and xG-per-shot actually dropped from his "
     "established level, or is this just a short-sample dip?"),
    (("important",),
     "matter as much as the hype suggests",
     "Do {player}'s team's underlying numbers change when he is on the pitch?"),
    (("overrated",),
     "deserve the hype",
     "Do {player}'s shot volume, xG and conversion this season match his "
     "reputation?"),
    (("clinical",),
     "finish as clinically as the reputation says",
     "Is {player}'s conversion rate running ahead of his xG by an amount "
     "that usually regresses?"),
    (("shoot", "shots"),
     "shoot too much",
     "Is {player} taking an unusually large share of his team's shots for "
     "his role?"),
    (("finish", "hot"),
     "finish better than expected, or just run hot",
     "Is {player}'s goals-minus-xG gap big enough to be a real finishing "
     "edge rather than variance?"),
]

DEFAULT_CLAIM: tuple[str, str] = (
    "live up to the claim",
    "Which specific, measurable version of this claim does the data support?",
)


def _infer_claim(text: str) -> tuple[str, str]:
    """Map a viral post to (vague claim verb, sharper testable question)."""
    lowered = text.lower()
    for keywords, claim_verb, sharper in CLAIM_TYPES:
        if any(k in lowered for k in keywords):
            return claim_verb, sharper
    return DEFAULT_CLAIM


def _slugify(text: str) -> str:
    text = text.lower().strip("?")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:40]


def run_discovery(reasoner: Reasoner, connectors: list[SourceConnector] | None = None,
                   limit: int = 10) -> list[Candidate]:
    """Full Discovery Agent pass: fetch -> cluster -> score -> rank."""
    connectors = connectors or default_connectors()
    posts: list[SourcePost] = []
    for connector in connectors:
        posts.extend(connector.fetch_posts())

    clusters = cluster_posts(posts)
    candidates = [build_candidate(player, cluster, reasoner) for player, cluster in clusters.items()]

    candidates.sort(key=lambda c: c.editorial_score, reverse=True)
    return candidates[:limit]
