"""Interactive debates data (see `cli.py debates` and templates/debates_app.html).

A debate is an A-vs-B football argument the reader explores in the debates
SPA: pick a side, weight the criteria, walk the evidence, get a weighted
verdict. Debates are hand-authored in data/debates.json — separate from the
story pipeline — and validated before they ship.

Field names and the tuple shapes inside `criteria` / `scenes` / `sources`
match the SPA's JS so the data drops straight in.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DEFAULT_SRC = DATA_DIR / "debates.json"
APP_TEMPLATE = REPO_ROOT / "templates" / "debates_app.html"
DEFAULT_SITE_ROOT = REPO_ROOT / "site"

_SLUG = re.compile(r"^[a-z0-9-]+$")
_URL = re.compile(r"^https?://", re.IGNORECASE)


@dataclass
class Debate:
    id: str
    tag: str
    title: str
    q: str
    a: str
    b: str
    teaser: str
    criteria: list   # [[key, label, weight, [scoreA, scoreB]], ...]
    scenes: list      # [[headline, body, metric, valA, valB, unit, insight], ...]
    sources: list     # [[label, url], ...]

    def to_dict(self) -> dict:
        return asdict(self)


def load_debates(path: Path | None = None) -> list[Debate]:
    path = Path(path or DEFAULT_SRC)
    raw = json.loads(path.read_text() or "[]")
    return [Debate(**item) for item in raw]


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int_0_100(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100


def validate_debates(debates: list[Debate]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for i, d in enumerate(debates):
        at = f"debate[{i}] ({d.id or '?'})"

        if not d.id or not _SLUG.match(d.id):
            errors.append(f"{at}: id must match [a-z0-9-]+")
        if d.id in seen_ids:
            errors.append(f"{at}: duplicate id")
        seen_ids.add(d.id)

        for field in ("tag", "title", "q", "a", "b", "teaser"):
            if not str(getattr(d, field, "") or "").strip():
                errors.append(f"{at}: {field} is empty")
        if d.a and d.b and d.a == d.b:
            errors.append(f"{at}: a and b are identical")

        if not isinstance(d.criteria, list) or not (3 <= len(d.criteria) <= 5):
            n = len(d.criteria) if isinstance(d.criteria, list) else "no"
            errors.append(f"{at}: needs 3-5 criteria, has {n}")
        else:
            seen_keys: set[str] = set()
            for j, c in enumerate(d.criteria):
                cat = f"{at} criteria[{j}]"
                if not isinstance(c, list) or len(c) != 4:
                    errors.append(f"{cat}: must be [key, label, weight, [scoreA, scoreB]]")
                    continue
                key, label, weight, scores = c
                if not isinstance(key, str) or not _SLUG.match(key or ""):
                    errors.append(f"{cat}: key must match [a-z0-9-]+")
                if key in seen_keys:
                    errors.append(f"{cat}: duplicate key '{key}'")
                seen_keys.add(key)
                if not str(label or "").strip():
                    errors.append(f"{cat}: label is empty")
                if not _int_0_100(weight):
                    errors.append(f"{cat}: weight must be an int in 0..100")
                if not (isinstance(scores, list) and len(scores) == 2
                        and all(_num(s) and 0 <= s <= 100 for s in scores)):
                    errors.append(f"{cat}: scores must be two numbers in 0..100")

        if not isinstance(d.scenes, list) or not (3 <= len(d.scenes) <= 5):
            n = len(d.scenes) if isinstance(d.scenes, list) else "no"
            errors.append(f"{at}: needs 3-5 scenes, has {n}")
        else:
            for j, s in enumerate(d.scenes):
                sat = f"{at} scenes[{j}]"
                if not isinstance(s, list) or len(s) != 7:
                    errors.append(f"{sat}: must have 7 fields "
                                  f"[headline, body, metric, valA, valB, unit, insight]")
                    continue
                for idx in (0, 1, 2, 5, 6):
                    if not str(s[idx] or "").strip():
                        errors.append(f"{sat}: field {idx} is empty")
                for idx in (3, 4):
                    if not _num(s[idx]):
                        errors.append(f"{sat}: field {idx} must be a number")

        if not isinstance(d.sources, list) or len(d.sources) < 1:
            errors.append(f"{at}: needs at least one source")
        else:
            for j, src in enumerate(d.sources):
                sat = f"{at} sources[{j}]"
                if not isinstance(src, list) or len(src) != 2:
                    errors.append(f"{sat}: must be [label, url]")
                    continue
                label, url = src
                if not str(label or "").strip():
                    errors.append(f"{sat}: label is empty")
                if not _URL.match(str(url or "")):
                    errors.append(f"{sat}: url must start with http:// or https://")

    return errors


def publish_debates(src: Path | None = None, site_root: Path | None = None) -> None:
    """Validate the debate source and write site/debates.json + site/index.html.

    Raises ValueError (with all errors joined) if the source does not validate.
    """
    src = Path(src or DEFAULT_SRC)
    site_root = Path(site_root or DEFAULT_SITE_ROOT)

    debates = load_debates(src)
    errors = validate_debates(debates)
    if errors:
        raise ValueError("Invalid debates:\n  - " + "\n  - ".join(errors))

    site_root.mkdir(parents=True, exist_ok=True)
    (site_root / "debates.json").write_text(
        json.dumps([d.to_dict() for d in debates], separators=(",", ":")) + "\n"
    )
    (site_root / "index.html").write_text(APP_TEMPLATE.read_text())
