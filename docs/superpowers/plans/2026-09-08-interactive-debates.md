# Interactive Debates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second product to the site — an interactive A-vs-B "debates" SPA (pick a side, weight the criteria, walk the evidence, get a weighted verdict) fed by a validated `debates.json`, alongside the unchanged story pipeline.

**Architecture:** A new `pipeline/debates.py` owns a `Debate` dataclass, a JSON loader, and a content validator. `data/debates.json` is hand-authored and committed. `cli.py debates publish` validates it and writes two files: `site/debates.json` (the data) and `site/index.html` (a verbatim copy of `templates/debates_app.html`, the reference MVP's SPA with its inline data swapped for a `fetch('debates.json')`). The existing story pipeline is unchanged except that its generated index and manifest move from `site/` down to `site/stories/`, freeing `site/` root for the debates app.

**Tech Stack:** Python 3.12 stdlib + Jinja2 (already a dependency; the debates app template is copied, not rendered). No new dependencies. Vanilla HTML/CSS/JS SPA, no build step. Tests: `python -m unittest discover -s tests`.

**Spec:** `docs/superpowers/specs/2026-09-05-interactive-debates-design.md`

## Global Constraints

- No new Python dependencies. `requirements.txt` stays `Jinja2` only; `opik` stays optional in `requirements-tracing.txt`.
- Tests run with `python -m unittest discover -s tests` and must all pass.
- The debates SPA has **no external dependencies, no build step, light theme only** — matching the reference at `docs/superpowers/specs/reference-mvp.html`.
- Debate JSON field names and the tuple shapes inside `criteria` / `scenes` / `sources` match the reference app's JS exactly (so the data drops straight in).
- `/` (i.e. `site/index.html`) is the debates app. The story index moves to `/stories/` (`site/stories/index.html`), its manifest to `site/stories/manifest.json`.
- The story pipeline's runtime behaviour is otherwise unchanged.
- Commit messages end with the two trailer lines used elsewhere in this repo:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_016QVS92GUaBwfEPXeaNHAyw
  ```

---

## File Structure

**Created:**
- `pipeline/debates.py` — `Debate` dataclass, `load_debates()`, `validate_debates()`, `publish_debates()`. One responsibility: debate data in, validated files out.
- `data/debates.json` — the committed debate content (hand-authored; seeded from the reference).
- `templates/debates_app.html` — the SPA: the reference MVP with `const debates=[…]` replaced by a `fetch`, plus a link to `/stories/`. No Jinja variables; copied verbatim on publish.
- `tests/test_debates.py` — validator unit tests, seed-file check, publish check, template guard.
- `.github/workflows/ci.yml` — run the test suite + `cli.py debates validate` on push/PR.

**Modified:**
- `cli.py` — add a `debates` subcommand group (`validate`, `publish [--commit]`).
- `pipeline/publish_agent.py` — `_update_index()` writes `site_root/stories/index.html` + `site_root/stories/manifest.json`; the `git add` list in `publish()` follows.
- `pipeline/orchestrator.py` — `_published_slugs()` reads `site_root/stories/manifest.json`.
- `templates/site_index.html.j2` — story-card `href` prefix `stories/<slug>/` → `<slug>/`; add a "← Play an argument" link to `../`.
- `tests/test_pipeline_smoke.py` — update the four `index.html` / `manifest.json` path assertions to `stories/…`.
- `README.md` — document the debates product and `cli.py debates`.
- `site/**` — regenerated in the final task.

---

## Task 1: `Debate` model, loader, and validator

**Files:**
- Create: `pipeline/debates.py`
- Test: `tests/test_debates.py`

**Interfaces:**
- Consumes: nothing (leaf module — imports only stdlib).
- Produces:
  - `Debate` dataclass with fields `id, tag, title, q, a, b, teaser` (all `str`), `criteria: list`, `scenes: list`, `sources: list`, and `.to_dict() -> dict`.
  - `DEFAULT_SRC: Path` = `<repo>/data/debates.json`.
  - `load_debates(path: Path | None = None) -> list[Debate]` — parses a JSON array of objects into `Debate`s.
  - `validate_debates(debates: list[Debate]) -> list[str]` — returns a list of human-readable error strings; empty list means valid.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_debates.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.debates import Debate, load_debates, validate_debates


def _debate(**overrides) -> Debate:
    base = dict(
        id="messi-ronaldo",
        tag="GOAT debate",
        title="Messi vs Ronaldo",
        q="Who is the best player in the world?",
        a="Lionel Messi",
        b="Cristiano Ronaldo",
        teaser="Scoring, creation and longevity pull the answer in different directions.",
        criteria=[
            ["scoring", "Scoring", 80, [96, 100]],
            ["creation", "Creation", 70, [100, 82]],
            ["longevity", "Longevity", 50, [88, 100]],
        ],
        scenes=[
            ["Start with totals", "Ronaldo leads the raw goal total.", "Career goals", 927, 978, "club + country", "A total is rate x opportunity."],
            ["Change the denominator", "Messi scores more often per game.", "Goals per game", 0.79, 0.73, "career", "Volume vs efficiency flips it."],
            ["Add creation", "Messi has more goal contributions.", "Goal contributions", 1348, 1239, "goals + assists", "Finishing and creating differ."],
        ],
        sources=[["FBref", "https://fbref.com/"]],
    )
    base.update(overrides)
    return Debate(**base)


class TestValidateDebates(unittest.TestCase):
    def test_a_well_formed_debate_has_no_errors(self):
        self.assertEqual(validate_debates([_debate()]), [])

    def test_duplicate_id_is_an_error(self):
        errs = validate_debates([_debate(), _debate()])
        self.assertTrue(any("duplicate id" in e for e in errs))

    def test_bad_id_characters_are_an_error(self):
        errs = validate_debates([_debate(id="Messi Ronaldo!")])
        self.assertTrue(any("id must match" in e for e in errs))

    def test_empty_title_is_an_error(self):
        errs = validate_debates([_debate(title="  ")])
        self.assertTrue(any("title is empty" in e for e in errs))

    def test_identical_sides_are_an_error(self):
        errs = validate_debates([_debate(a="Messi", b="Messi")])
        self.assertTrue(any("a and b are identical" in e for e in errs))

    def test_too_few_and_too_many_criteria_are_errors(self):
        two = _debate(criteria=_debate().criteria[:2])
        six = _debate(criteria=_debate().criteria + _debate().criteria)
        self.assertTrue(any("3-5 criteria" in e for e in validate_debates([two])))
        self.assertTrue(any("3-5 criteria" in e for e in validate_debates([six])))

    def test_criterion_weight_out_of_range_is_an_error(self):
        d = _debate()
        d.criteria[0][2] = 150
        self.assertTrue(any("weight must be an int in 0..100" in e for e in validate_debates([d])))

    def test_criterion_score_out_of_range_is_an_error(self):
        d = _debate()
        d.criteria[0][3] = [-5, 100]
        self.assertTrue(any("scores must be two numbers in 0..100" in e for e in validate_debates([d])))

    def test_duplicate_criterion_key_is_an_error(self):
        d = _debate()
        d.criteria[1][0] = d.criteria[0][0]
        self.assertTrue(any("duplicate key" in e for e in validate_debates([d])))

    def test_scene_with_wrong_field_count_is_an_error(self):
        d = _debate()
        d.scenes[0] = d.scenes[0][:6]
        self.assertTrue(any("7 fields" in e for e in validate_debates([d])))

    def test_scene_with_non_numeric_value_is_an_error(self):
        d = _debate()
        d.scenes[0][3] = "lots"
        self.assertTrue(any("must be a number" in e for e in validate_debates([d])))

    def test_source_url_without_scheme_is_an_error(self):
        errs = validate_debates([_debate(sources=[["FBref", "fbref.com"]])])
        self.assertTrue(any("http" in e for e in errs))

    def test_empty_sources_is_an_error(self):
        errs = validate_debates([_debate(sources=[])])
        self.assertTrue(any("at least one source" in e for e in errs))


class TestLoadDebates(unittest.TestCase):
    def test_round_trips_a_json_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "debates.json"
            p.write_text(json.dumps([_debate().to_dict()]))
            loaded = load_debates(p)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].id, "messi-ronaldo")
            self.assertEqual(validate_debates(loaded), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_debates -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.debates'`

- [ ] **Step 3: Write the implementation**

Create `pipeline/debates.py`:

```python
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
from dataclasses import asdict, dataclass
from pathlib import Path
import re

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_SRC = DATA_DIR / "debates.json"

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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_debates -v`
Expected: PASS (all 15 tests)

- [ ] **Step 5: Run the full suite to check nothing regressed**

Run: `python -m unittest discover -s tests`
Expected: OK — 38 existing + 15 new.

- [ ] **Step 6: Commit**

```bash
git add pipeline/debates.py tests/test_debates.py
git commit -m "Add Debate model, loader and content validator

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016QVS92GUaBwfEPXeaNHAyw"
```

---

## Task 2: Seed `data/debates.json`

**Files:**
- Create: `data/debates.json`
- Test: `tests/test_debates.py` (add one test)

**Interfaces:**
- Consumes: `load_debates`, `validate_debates`, `DEFAULT_SRC` from Task 1.
- Produces: `data/debates.json` — a 4-element JSON array that passes `validate_debates`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_debates.py` (new class at the end, before `if __name__`):

```python
class TestSeedFile(unittest.TestCase):
    def test_committed_debates_json_is_valid(self):
        from pipeline.debates import DEFAULT_SRC
        debates = load_debates(DEFAULT_SRC)
        self.assertGreaterEqual(len(debates), 3)
        self.assertEqual(validate_debates(debates), [])
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m unittest tests.test_debates.TestSeedFile -v`
Expected: FAIL — `FileNotFoundError` on `data/debates.json`.

- [ ] **Step 3: Generate the seed file from the reference**

Run this exact command from the repo root (extracts the reference app's `debates` array and pretty-prints it):

```bash
python - <<'PY'
import json
from pathlib import Path
h = Path("docs/superpowers/specs/reference-mvp.html").read_text()
i = h.index("const debates=") + len("const debates=")
j = h.index("];", i) + 1
arr = json.loads(h[i:j])
Path("data/debates.json").write_text(json.dumps(arr, indent=2) + "\n")
print(f"wrote {len(arr)} debates: {[d['id'] for d in arr]}")
PY
```

Expected output: `wrote 4 debates: ['messi', 'coaches', 'midfield', 'teams']`

Then rename the ids to be more descriptive (the validator only requires `[a-z0-9-]+`, but readable ids help). Edit `data/debates.json` and change the four `"id"` values:
- `"messi"` → `"messi-ronaldo"`
- `"coaches"` → `"guardiola-luis-enrique"`
- `"midfield"` → `"xavi-iniesta"`
- `"teams"` → `"barca-2011-madrid-2017"`

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.test_debates.TestSeedFile -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: OK

- [ ] **Step 6: Commit**

```bash
git add data/debates.json tests/test_debates.py
git commit -m "Seed data/debates.json with four football debates

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016QVS92GUaBwfEPXeaNHAyw"
```

---

## Task 3: The debates SPA template + `publish_debates()`

**Files:**
- Create: `templates/debates_app.html`
- Modify: `pipeline/debates.py` (add `publish_debates`)
- Test: `tests/test_debates.py` (add a class)

**Interfaces:**
- Consumes: `load_debates`, `validate_debates`, `DEFAULT_SRC` from Task 1.
- Produces:
  - `templates/debates_app.html` — the SPA. Contains the string `fetch(` and does **not** contain `const debates=[`.
  - `publish_debates(src: Path | None = None, site_root: Path | None = None) -> None` in `pipeline/debates.py`. Loads `src` (default `DEFAULT_SRC`), runs `validate_debates`, raises `ValueError` with the newline-joined errors if any, then writes `site_root/debates.json` (compact JSON) and `site_root/index.html` (verbatim copy of `templates/debates_app.html`). Default `site_root` is `<repo>/site`.

- [ ] **Step 1: Create the SPA template**

Create `templates/debates_app.html` by copying `docs/superpowers/specs/reference-mvp.html` and making exactly three edits:

Run:

```bash
cp docs/superpowers/specs/reference-mvp.html templates/debates_app.html
```

**Edit 1 — swap inline data for a fetch.** In `templates/debates_app.html`, find the `<script>` that begins:

```
<script>const debates=[{"id": "messi", ...}];let S={d:null,...
```

Replace the segment `const debates=[…];` (the entire array literal, ending at `}];`) with:

```
let debates=[];
```

so the script now starts `<script>let debates=[];let S={d:null,...`.

**Edit 2 — load the data before rendering.** At the very end of that same `<script>`, replace the trailing `home();</script>` with:

```
fetch("debates.json").then(r=>r.json()).then(d=>{debates=d;home()}).catch(()=>{document.getElementById("cards").innerHTML='<p class="lead">Couldn\'t load debates.</p>'});</script>
```

**Edit 3 — link to the stories product.** In the `home` section markup, find:

```
<p class="lead">Pick a classic debate, commit to an answer, then define what <em>better</em> actually means. The data may confirm your bias — or expose it.</p>
```

and add, immediately after it:

```
<p class="small"><a href="stories/">Prefer a long read? Data stories &rarr;</a></p>
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_debates.py`:

```python
class TestPublishDebates(unittest.TestCase):
    def test_publish_writes_data_and_app(self):
        from pipeline.debates import publish_debates, DEFAULT_SRC
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            publish_debates(DEFAULT_SRC, site)
            data = json.loads((site / "debates.json").read_text())
            self.assertEqual(len(data), len(load_debates(DEFAULT_SRC)))
            app = (site / "index.html").read_text()
            self.assertIn("fetch(", app)
            self.assertNotIn("const debates=[", app)

    def test_publish_rejects_invalid_source(self):
        from pipeline.debates import publish_debates
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "bad.json"
            src.write_text(json.dumps([_debate(id="Bad Id").to_dict()]))
            with self.assertRaises(ValueError):
                publish_debates(src, Path(tmp))


class TestAppTemplate(unittest.TestCase):
    def test_template_fetches_and_has_no_inline_data(self):
        from pathlib import Path
        tpl = Path("templates/debates_app.html").read_text()
        self.assertIn('fetch("debates.json")', tpl)
        self.assertNotIn("const debates=[", tpl)
        self.assertIn('href="stories/"', tpl)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m unittest tests.test_debates.TestPublishDebates tests.test_debates.TestAppTemplate -v`
Expected: `TestAppTemplate` PASSES (template already edited in Step 1); `TestPublishDebates` FAILS — `ImportError: cannot import name 'publish_debates'`.

- [ ] **Step 4: Implement `publish_debates`**

Append to `pipeline/debates.py`:

```python
REPO_ROOT = Path(__file__).resolve().parent.parent
APP_TEMPLATE = REPO_ROOT / "templates" / "debates_app.html"
DEFAULT_SITE_ROOT = REPO_ROOT / "site"


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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m unittest tests.test_debates -v`
Expected: PASS (all classes)

- [ ] **Step 6: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: OK

- [ ] **Step 7: Commit**

```bash
git add templates/debates_app.html pipeline/debates.py tests/test_debates.py
git commit -m "Add debates SPA template and publish_debates()

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016QVS92GUaBwfEPXeaNHAyw"
```

---

## Task 4: `cli.py debates` subcommands

**Files:**
- Modify: `cli.py`
- Test: `tests/test_debates.py` (add a class)

**Interfaces:**
- Consumes: `validate_debates`, `load_debates`, `publish_debates`, `DEFAULT_SRC` from Tasks 1 & 3.
- Produces: CLI `python cli.py debates validate` (exit 1 on any error, printing each) and `python cli.py debates publish [--commit]` (validates, writes `site/`, and with `--commit` runs `git add site/index.html site/debates.json` + `git commit`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_debates.py`:

```python
class TestDebatesCli(unittest.TestCase):
    def test_validate_subcommand_passes_on_the_seed_file(self):
        import subprocess
        r = subprocess.run(
            ["python", "cli.py", "debates", "validate"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)

    def test_publish_subcommand_writes_site_files(self):
        import subprocess
        r = subprocess.run(
            ["python", "cli.py", "debates", "publish"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertTrue(Path("site/debates.json").exists())
        self.assertTrue(Path("site/index.html").exists())
```

Note: `test_publish_subcommand_writes_site_files` writes into the real `site/`. That is intentional — it is exercised again and committed in Task 6. It is idempotent.

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m unittest tests.test_debates.TestDebatesCli -v`
Expected: FAIL — `cli.py: error: argument command: invalid choice: 'debates'`

- [ ] **Step 3: Add the subcommand group to `cli.py`**

In `cli.py`, after the `submissions` subparser block (`subs_p = sub.add_parser("submissions", …)` and its `add_argument`), add:

```python
    debates_p = sub.add_parser("debates", help="Validate / publish the interactive debates")
    debates_sub = debates_p.add_subparsers(dest="debates_command", required=True)
    debates_sub.add_parser("validate", help="Check data/debates.json")
    pub_p = debates_sub.add_parser("publish", help="Write site/debates.json + site/index.html")
    pub_p.add_argument("--commit", action="store_true",
                       help="Stage + commit the published files locally.")
```

Then, in `main()`, after the `if args.command == "submissions":` block and before `if args.command == "run":`, add:

```python
    if args.command == "debates":
        import subprocess

        from pipeline.debates import (
            DEFAULT_SRC, load_debates, publish_debates, validate_debates,
        )

        errors = validate_debates(load_debates(DEFAULT_SRC))
        if errors:
            print("data/debates.json is invalid:")
            for e in errors:
                print(f"  - {e}")
            return 1

        if args.debates_command == "validate":
            print(f"OK — {len(load_debates(DEFAULT_SRC))} debates valid.")
            return 0

        publish_debates()
        print("Wrote site/debates.json and site/index.html")
        if args.debates_command == "publish" and args.commit:
            subprocess.run(["git", "add", "site/index.html", "site/debates.json"], check=True)
            subprocess.run(["git", "commit", "-m", "Publish debates"], check=True)
        return 0
```

Also update the module docstring at the top of `cli.py` — add these lines to the usage block:

```
    python cli.py debates validate                            # check data/debates.json
    python cli.py debates publish                             # write site/index.html + site/debates.json
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest tests.test_debates.TestDebatesCli -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: OK. (`site/debates.json` and a debates `site/index.html` now exist locally — that is fine, Task 5 and 6 rebuild `site/` deliberately.)

- [ ] **Step 6: Commit**

```bash
git add cli.py tests/test_debates.py
git commit -m "Add 'cli.py debates validate|publish'

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016QVS92GUaBwfEPXeaNHAyw"
```

---

## Task 5: Move the story index under `site/stories/`

**Files:**
- Modify: `pipeline/publish_agent.py:35-49` (`_update_index`), `pipeline/publish_agent.py:74-76` (the `git add` list)
- Modify: `pipeline/orchestrator.py:40-46` (`_published_slugs`)
- Modify: `templates/site_index.html.j2`
- Modify: `tests/test_pipeline_smoke.py` (four assertions)

**Interfaces:**
- Consumes: nothing new.
- Produces: after a pipeline run, `site_root/stories/index.html` and `site_root/stories/manifest.json` exist (not `site_root/index.html` / `site_root/manifest.json`). Story-card links in that index are `<slug>/` (relative to `stories/`).

- [ ] **Step 1: Update the four smoke-test assertions**

In `tests/test_pipeline_smoke.py`:

- Line 45: `site_index = (self.tmp / "index.html").read_text()` → `site_index = (self.tmp / "stories" / "index.html").read_text()`
- Line 47: `self.assertIn(f"stories/{published['slug']}/", site_index)` → `self.assertIn(f"{published['slug']}/", site_index)`
- Line 48: `manifest = json.loads((self.tmp / "manifest.json").read_text())` → `manifest = json.loads((self.tmp / "stories" / "manifest.json").read_text())`
- Line 60: `self.assertTrue((self.tmp / "index.html").exists())` → `self.assertTrue((self.tmp / "stories" / "index.html").exists())`
- Line 75: `self.assertTrue((site_root / "index.html").exists())` → `self.assertTrue((site_root / "stories" / "index.html").exists())`
- Line 77: `self.assertFalse((output_root / "index.html").exists())` → `self.assertFalse((output_root / "stories" / "index.html").exists())` — wait, this line asserts the *output* root has no index; keep it asserting `output_root / "index.html"` does not exist AND add `self.assertFalse((output_root / "stories" / "index.html").exists())` is wrong because output_root has no site at all. Leave line 77 as-is (`output_root / "index.html"` still must not exist).

- [ ] **Step 2: Run the smoke tests to verify they fail**

Run: `python -m unittest tests.test_pipeline_smoke -v`
Expected: FAIL — files are still written to `self.tmp / "index.html"`, not `self.tmp / "stories" / "index.html"`.

- [ ] **Step 3: Update `_update_index` in `pipeline/publish_agent.py`**

Replace the body of `_update_index` (currently `pipeline/publish_agent.py:35-49`):

```python
def _update_index(site_root: Path, story: StorySpec) -> None:
    stories_root = site_root / "stories"
    stories_root.mkdir(parents=True, exist_ok=True)
    manifest_path = stories_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    manifest = [entry for entry in manifest if entry["slug"] != story.slug]
    manifest.append({
        "slug": story.slug,
        "title": story.title,
        "dek": story.dek,
        "published_at": datetime.now(timezone.utc).isoformat(),
    })
    manifest.sort(key=lambda entry: entry["published_at"], reverse=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))

    template = _env.get_template("site_index.html.j2")
    (stories_root / "index.html").write_text(template.render(stories=manifest))
```

- [ ] **Step 4: Update the `git add` list in `publish()`**

In `pipeline/publish_agent.py` (currently lines 74-76), change:

```python
        subprocess.run(
            ["git", "add", str(published_path), str(site_root / "index.html"),
             str(site_root / "manifest.json")],
            check=True, cwd=site_root.parent,
        )
```

to:

```python
        subprocess.run(
            ["git", "add", str(published_path),
             str(site_root / "stories" / "index.html"),
             str(site_root / "stories" / "manifest.json")],
            check=True, cwd=site_root.parent,
        )
```

- [ ] **Step 5: Update `_published_slugs` in `pipeline/orchestrator.py`**

Change (currently lines 40-46):

```python
def _published_slugs(site_root: Path) -> set[str]:
    manifest = site_root / "manifest.json"
```

to:

```python
def _published_slugs(site_root: Path) -> set[str]:
    manifest = site_root / "stories" / "manifest.json"
```

- [ ] **Step 6: Update `templates/site_index.html.j2`**

Two changes:

1. The story link — find `<a class="story-card" href="stories/{{ story.slug }}/">` and change to `<a class="story-card" href="{{ story.slug }}/">`.

2. Add a back-link to the debates app. Immediately after `<h1>Football data stories</h1>` add:

```
  <p class="intro"><a href="../">&larr; Play an argument</a></p>
```

(If an existing `<p class="intro">…</p>` line is already there, add the link inside it rather than adding a second one.)

- [ ] **Step 7: Run the smoke tests to verify they pass**

Run: `python -m unittest tests.test_pipeline_smoke -v`
Expected: PASS

- [ ] **Step 8: Run the full suite**

Run: `python -m unittest discover -s tests`
Expected: OK — all tests (existing + Tasks 1–4).

- [ ] **Step 9: Commit**

```bash
git add pipeline/publish_agent.py pipeline/orchestrator.py templates/site_index.html.j2 tests/test_pipeline_smoke.py
git commit -m "Move the story index+manifest under site/stories/

Frees site/ root for the debates app.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016QVS92GUaBwfEPXeaNHAyw"
```

---

## Task 6: Regenerate `site/`, add CI, deploy

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `site/**` (regenerated)

**Interfaces:**
- Consumes: `cli.py debates publish`, `scripts/seed_demo_stories.py` (existing), Tasks 1–5.
- Produces: a coherent `site/` (debates app at root, stories under `stories/`), a CI workflow, updated README.

- [ ] **Step 1: Add the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m unittest discover -s tests
      - run: python cli.py debates validate
```

- [ ] **Step 2: Rebuild the whole site**

Run from the repo root:

```bash
rm -rf site
python cli.py debates publish
python scripts/seed_demo_stories.py -n 5
```

Expected: `site/index.html` (debates app), `site/debates.json`, `site/stories/index.html`, `site/stories/manifest.json`, `site/stories/<slug>/index.html` ×5.

- [ ] **Step 3: Sanity-check the output**

```bash
test -f site/index.html && grep -q 'fetch("debates.json")' site/index.html && echo "app ok"
python -c "import json; assert len(json.load(open('site/debates.json'))) == 4; print('data ok')"
test -f site/stories/index.html && grep -q 'Play an argument' site/stories/index.html && echo "stories index ok"
ls site/stories/*/index.html | wc -l   # expect 5
```

Expected: `app ok`, `data ok`, `stories index ok`, `5`.

- [ ] **Step 4: Update the README**

In `README.md`, under the "Pipeline stages -> code" table area or a new top-level section, add:

```markdown
## Two products

- **Stories** (`/stories/`) — the pipeline output: viral-debate questions
  taken through discovery, the two human gates, and rendered as
  scrollytelling. Built by `cli.py run` / `scripts/seed_demo_stories.py`.
- **Debates** (`/`) — an interactive A-vs-B argument tool: pick a side,
  weight the criteria that matter to you, walk the evidence, get a verdict
  that reacts to your weighting. Data is hand-authored in
  `data/debates.json`; `cli.py debates publish` validates it and writes
  `site/index.html` + `site/debates.json`.

```bash
python cli.py debates validate          # check data/debates.json
python cli.py debates publish            # write the app + data into site/
```
```

Also update any line in the README that says the story index is at `site/index.html` — it is now `site/stories/index.html`.

- [ ] **Step 5: Run the full suite one more time**

Run: `python -m unittest discover -s tests`
Expected: OK

- [ ] **Step 6: Commit and push**

```bash
git add .github/workflows/ci.yml README.md site
git commit -m "Regenerate site with the debates app at root; add CI

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_016QVS92GUaBwfEPXeaNHAyw"
git push
```

- [ ] **Step 7: Verify the deploy**

Wait for the `pages.yml` workflow run to finish (`gh run list --workflow=pages.yml -L 1`), then:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://menpente.github.io/football-arguments-lab/            # 200
curl -sS https://menpente.github.io/football-arguments-lab/debates.json | python -c "import sys,json; print(len(json.load(sys.stdin)), 'debates')"
curl -sS -o /dev/null -w '%{http_code}\n' https://menpente.github.io/football-arguments-lab/stories/     # 200
```

- [ ] **Step 8: Manual walk-through**

Open https://menpente.github.io/football-arguments-lab/ and confirm: the four debate cards load; pick one → choose a side + confidence → weight the criteria → step through the scenes with the sticky bar chart → verdict screen shows the weighted scores and the "instinct survives / criteria changed the winner" line; the "Data stories →" link reaches `/stories/`, which links back.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task |
|---|---|
| Site structure (`/` debates, `/stories/` index) | Tasks 3, 5, 6 |
| `publish_agent` index move | Task 5 |
| `_published_slugs` path | Task 5 |
| Debate data model / `data/debates.json` | Tasks 1, 2 |
| `pipeline/debates.py` (`Debate`, `load_debates`, `validate_debates`, `publish_debates`) | Tasks 1, 3 |
| Validator rules 1–5 | Task 1 (tests cover each) |
| `cli.py debates validate|publish [--commit]` | Task 4 |
| SPA template (fetch swap, stories link, keep palette/flow) | Task 3 |
| `tests/test_debates.py` cases | Tasks 1–4 |
| `test_pipeline_smoke.py` path fixes | Task 5 |
| `.github/workflows/ci.yml` | Task 6 |
| README | Task 6 |
| Regenerate site | Task 6 |

No gaps.

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Every code step has literal code. The one judgement call (readable ids in Task 2 Step 3) has the exact rename list.

**3. Type consistency:** `Debate` fields and `publish_debates(src, site_root)` signature are identical across Tasks 1, 3, 4. `validate_debates(list[Debate]) -> list[str]` used consistently. `_update_index(site_root, story)` keeps its signature in Task 5. Manifest path `site_root/"stories"/"manifest.json"` matches between `publish_agent` and `orchestrator`.

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute the tasks in this session with checkpoints.

Which approach?
