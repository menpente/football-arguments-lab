"""Reader-submitted questions (see `cli.py submit`).

A submission is a free-text question a reader or editor wants the pipeline
to consider. It is stored in a JSON file (git is the persistence — no DB,
no hosting) and, on the next run, turned into a `Candidate` that appears in
its own section of the Human Gate #1 slate, unscored: the editorial-score
formula assumes viral-post engagement signal, which a submission has none
of, so the editor judges these directly.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .models import Candidate, Submission
from .reasoner import Reasoner
from .refiner import refine_question
from .tracing import traced

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_PATH = DATA_DIR / "submissions.json"


def load_submissions(path: Path | None = None) -> list[Submission]:
    path = path or DEFAULT_PATH
    if not path.exists():
        return []
    raw = json.loads(path.read_text() or "[]")
    return [Submission(**item) for item in raw]


def save_submissions(submissions: list[Submission], path: Path | None = None) -> None:
    path = path or DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([s.to_dict() for s in submissions], indent=2) + "\n"
    )


def add_submission(question: str, note: str = "", path: Path | None = None) -> Submission:
    """Append a new submission and persist it. Returns the stored record."""
    submission = Submission(
        id=f"sub-{uuid.uuid4().hex[:8]}",
        question=_normalise_question(question),
        note=note.strip(),
    )
    existing = load_submissions(path)
    existing.append(submission)
    save_submissions(existing, path)
    return submission


def _normalise_question(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        raise ValueError("Submission question is empty.")
    return text if text.endswith("?") else f"{text}?"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@traced(name="submissions_to_candidates")
def to_candidates(submissions: list[Submission], reasoner: Reasoner,
                   published_slugs: set[str] | None = None) -> list[Candidate]:
    """Turn every ``new`` submission into an unscored, reader-submitted Candidate.

    Submissions whose question already matches a published story slug are
    skipped (light dedup).
    """
    published_slugs = published_slugs or set()
    candidates: list[Candidate] = []
    for sub in submissions:
        if sub.status != "new":
            continue
        if _slug(sub.question.rstrip("?")) in published_slugs:
            continue
        refined = refine_question(sub.question, sub.question, [], reasoner)
        candidates.append(
            Candidate(
                id=sub.id,
                question=sub.question,
                source_posts=[],
                source_summary=f"Reader-submitted via CLI on {sub.submitted_at[:10]}.",
                pitch=sub.note or "A reader asked for this one.",
                better_question=refined.question,
                possible_dimensions=[],
                boring_risk="No viral signal to lean on — the editor decides if "
                            "it is worth a story.",
                social_signal=0.0,
                question_quality=0.0,
                data_feasibility=0.0,
                story_potential=0.0,
                surprise_potential=0.0,
                editorial_score=0.0,
                refinement_rationale=refined.rationale,
                reader_submitted=True,
            )
        )
    return candidates
