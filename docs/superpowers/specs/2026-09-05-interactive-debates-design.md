# Interactive debates product — design

Status: approved for planning · 2026-09-05

Reference: <https://football-arguments-lab-mvp.vercel.app/> (the target look and
interaction; its source is the basis for the SPA).

Tracking: GitHub issue #3 (restyle) is subsumed by this; #4 (submission form)
moves with the story index.

## Goal

Add a second, interactive product to the site — an "arguments" app where a
reader picks a side of an A-vs-B football debate, commits a confidence level,
weights the criteria that matter to them, walks the evidence scene by scene,
and gets a weighted verdict that reacts to their own weighting.

The existing story pipeline (discovery → gates → scrollytelling HTML) is
**unchanged in behaviour**. Debates are authored separately from it.

## Non-goals

- Reshaping the story pipeline into A-vs-B debates.
- An LLM debate generator (separate follow-up issue).
- Dark theme for the debates app (the reference is light-only; match it).
- Persisting a reader's choices/weights server-side.

## Architecture

Two products, one `site/` tree deployed by the existing
`.github/workflows/pages.yml` (already triggers on `site/**`).

| URL | What | Produced from |
|---|---|---|
| `/` | The debates SPA | `templates/debates_app.html.j2` → `site/index.html` |
| `/debates.json` | Debate data the SPA fetches at load | `data/debates.json` → validated copy `site/debates.json` |
| `/stories/` | Story list + "Ask your own" submission form | `templates/site_index.html.j2` → `site/stories/index.html` |
| `/stories/<slug>/` | Pipeline scrollytelling stories | `pipeline/artifact_agent` (unchanged) |

Cross-links: the debates home screen links to `/stories/`; the stories index
links back to `/`.

### Change to `pipeline/publish_agent.py`

`_update_index` currently writes `site/index.html` from `site_index.html.j2`
and `site/manifest.json`. Both move under `site/stories/`:
`site/stories/index.html` and `site/stories/manifest.json`. Story-card hrefs
are already relative (`stories/<slug>/` → becomes `<slug>/`), so the
template's link prefix is adjusted.

`orchestrator._published_slugs()` reads the manifest — update its path to
`site/stories/manifest.json`.

## Debate data model

`data/debates.json` is a JSON array. Each entry (field names and tuple shapes
match the reference app so its JS ports with minimal change):

```json
{
  "id": "messi-ronaldo",
  "tag": "GOAT debate",
  "title": "Messi vs Ronaldo",
  "q": "Who is the best player in the world?",
  "a": "Lionel Messi",
  "b": "Cristiano Ronaldo",
  "teaser": "Scoring, creation and longevity pull the answer in different directions.",
  "criteria": [
    ["scoring", "Scoring", 80, [96, 100]],
    ["creation", "Creation", 70, [100, 82]],
    ["longevity", "Longevity", 50, [88, 100]]
  ],
  "scenes": [
    ["Start with totals", "Ronaldo leads the raw goal total.", "Career goals", 927, 978, "club + country", "A total is rate x opportunity."]
  ],
  "sources": [
    ["FBref", "https://fbref.com/..."]
  ]
}
```

- `criteria`: 3–5 entries, each `[key, label, defaultWeight, [scoreA, scoreB]]`.
  `key` slug-safe and unique within the debate; `label` non-empty;
  `defaultWeight` int 0–100; `scoreA`/`scoreB` numbers 0–100 (already
  normalised within the pair by the author).
- `scenes`: 3–5 entries, each
  `[headline, body, metricTitle, valueA, valueB, unit, insight]` — first three
  and last two are non-empty strings, `valueA`/`valueB` numbers.
- `sources`: ≥1 entry, each `[label, url]` with an `http`/`https` url.

Hand-authored and committed. Seeded with ~4 football debates (the reference
app's four are a fine starting set: Messi/Ronaldo, Guardiola/Luis Enrique,
Xavi/Iniesta, Barça 2011/Madrid 2017 — refreshed sources).

## `pipeline/debates.py`

```
@dataclass
class Debate:
    id: str
    tag: str
    title: str
    q: str
    a: str
    b: str
    teaser: str
    criteria: list[list]     # [[key, label, weight, [scoreA, scoreB]], ...]
    scenes: list[list]       # [[headline, body, metric, valA, valB, unit, insight], ...]
    sources: list[list]      # [[label, url], ...]
    def to_dict(self) -> dict: ...

def load_debates(path: Path | None = None) -> list[Debate]
def validate_debates(debates: list[Debate]) -> list[str]   # human-readable errors, empty == ok
def publish_debates(src: Path | None = None, site_root: Path | None = None) -> None
    # loads src (data/debates.json), validates (raises ValueError with the
    # joined errors on failure), then writes site_root/debates.json (compact
    # JSON array) and site_root/index.html (from templates/debates_app.html.j2)
```

`validate_debates` checks, per debate, in this order, collecting all errors:

1. `id` present, slug-safe (`^[a-z0-9-]+$`), unique across the file.
2. `tag`, `title`, `q`, `a`, `b`, `teaser` non-empty strings; `a != b`.
3. `criteria`: length 3–5; each a 4-element list; `key` slug-safe & unique in
   the debate; `label` non-empty; `weight` int in [0, 100]; scores a 2-element
   list of numbers each in [0, 100].
4. `scenes`: length 3–5; each a 7-element list; strings at indexes 0,1,2,5,6
   non-empty; numbers at 3,4.
5. `sources`: length ≥ 1; each `[label, url]`, label non-empty, url matches
   `^https?://`.

## `cli.py debates`

```
python cli.py debates validate            # run validate_debates, print errors, exit 1 on any
python cli.py debates publish [--commit]   # validate + write site/debates.json; --commit stages it
```

Wired into `main()` alongside the existing `run` / `submit` / `submissions`
subcommands.

## The SPA — `templates/debates_app.html.j2`

Start from the reference app's single-file HTML/CSS/JS. Changes:

1. Replace the inline `const debates = [ ... ];` with a load step:
   `fetch('debates.json').then(r => r.json()).then(data => { debates = data; home(); })`.
   Show a minimal "Loading debates…" / "Couldn't load debates." state.
2. On the `home` screen add a link: `Prefer a long read? → Data stories`
   pointing at `stories/`.
3. Keep everything else: the `--paper/--ink/--blue/--red` palette, Georgia +
   Arial fonts, the six `.screen`s (`home`, `pick`, `define`, `story`,
   `result`), the sticky progress bar, the sticky two-bar chart, the `calc()`
   weighted-score function, and the verdict copy
   ("Your instinct survives the data." / "Your own criteria changed the
   winner.").
4. No external dependencies; no build step; light theme only.

Rendered to `site/index.html`. The template has no per-debate Jinja variables
(data comes from the fetch), so "rendering" is effectively a copy — but keep it
as a template file under `templates/` for consistency and so a future header/
footer partial can be shared with the story template. `publish_debates` writes
**both** outputs: `site/index.html` (from the template) and `site/debates.json`
(the validated data).

Decision: `/` is the debates app itself, not a landing page. The reference
app's root is the app; a reader who wants stories takes the one link.

## Tests

`tests/test_debates.py`:

- `validate_debates` returns errors for: duplicate id, bad id chars, empty
  `title`, `a == b`, 2 criteria, 6 criteria, a criterion weight of 150, a
  criterion score of -5, a 6-element scene, a non-numeric scene value, a
  source url without a scheme, an empty sources list.
- The committed `data/debates.json` passes `validate_debates` with no errors.
- `publish_debates` writes a `site/debates.json` that re-parses and re-passes
  validation, and whose entry count matches the source.
- A tiny check that `templates/debates_app.html.j2` contains `fetch(` and does
  **not** contain `const debates=[` (guards against re-inlining data).

Update `tests/test_pipeline_smoke.py` for the `site/stories/index.html` and
`site/stories/manifest.json` paths.

## CI

New `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python -m unittest discover -s tests
      - run: python cli.py debates validate
```

(There is no test CI today; this also protects the existing 38 tests.)

## Rollout

1. `pipeline/debates.py` + tests (red → green).
2. `data/debates.json` seeded + passing.
3. `cli.py debates` subcommands.
4. `templates/debates_app.html.j2` from the reference app + fetch wiring.
5. `publish_agent` index move + `site_index.html.j2` → stories sub-index +
   cross-links; fix smoke tests.
6. `publish_debates` writes `site/index.html` + `site/debates.json`;
   regenerate the full `site/`.
7. `ci.yml`.
8. Commit, push, confirm Pages deploy; manual walk-through of the flow.

## Risks / open questions

- The reference app's four debates are player/manager/team GOAT arguments, not
  the "is claim X true" shape the story pipeline chases. That's fine — the two
  products have different framings by design — but the seed content is
  effectively new authoring work.
- Moving `/` from the story index to the debates app changes what a returning
  visitor sees. Acceptable per the decision above; the story index stays one
  click away and keeps its URL structure under `/stories/`.
- `site/index.html` is currently regenerated by the story pipeline. After this
  change nothing in the story pipeline touches `site/index.html`; only
  `cli.py debates publish` does. Keep that ownership boundary clear in code
  comments.
