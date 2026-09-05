# Football Editorial Agent

A working prototype of the agentic editorial workflow described in the
product spec: discover promising football data-story questions, let a human
editor pick and refine one, research and validate the data, generate a
scrollytelling artifact, run automated QA, get final human sign-off, and
publish.

**Published site:** https://menpente.github.io/football-arguments-lab/

The human editor still owns question selection, framing, and publish
approval — the pipeline only automates discovery, research, drafting, QA,
and deployment mechanics, pausing at two gates for a person.

## Pipeline stages -> code

| Spec section | Stage | Module |
|---|---|---|
| 4-6 | Discovery + Candidate Scoring | `pipeline/discovery.py` |
| 6 | Question Refiner Agent (sharper question + rationale for Gate #1) | `pipeline/refiner.py` |
| 7 | Human Gate #1 (approve/refine/hold/reject) | `pipeline/gates.py` |
| 8 | Question Agent (research brief) | `pipeline/question_agent.py` |
| 9 | Data/Research Agent | `pipeline/data_agent.py` |
| 10 | Data validation | `pipeline/validation.py` |
| 11 | Story Agent (narrative spec) | `pipeline/story_agent.py` |
| 12 | Artifact Agent (scrollytelling HTML) | `pipeline/artifact_agent.py`, `pipeline/charts.py`, `templates/` |
| 13 | QA Agent | `pipeline/qa_agent.py` |
| — | Human Gate #2 (approve/revise/kill) | `pipeline/gates.py` |
| 14 | Publish Agent | `pipeline/publish_agent.py`, `.github/workflows/pages.yml` |

`pipeline/orchestrator.py` wires all of the above into one run, matching the
section 3 architecture diagram. `pipeline/models.py` holds dataclasses that
serialize to exactly the JSON shapes in the spec (sections 5, 8, 9, 10).

## Quickstart

```bash
pip install -r requirements.txt   # just Jinja2

# Interactive: you play both human gates at the terminal
python cli.py run

# Scripted demo: auto-approves the top-scored candidate, no prompts
python cli.py run --auto

# Same, plus a local git commit of the published artifact
python cli.py run --auto --commit

# Populate the demo site with the top few candidates in one pass
python scripts/seed_demo_stories.py            # dry run, writes site/ only
python scripts/seed_demo_stories.py -n 3 --commit
```

A successful run writes:

- `output/runs/<slug>/` — the research brief, dataset, validation result,
  story spec, and QA report for that story, as JSON. Ephemeral, gitignored.
- `output/last_run.json` — the full run log (candidates considered, gate
  decisions, what got blocked and why). Ephemeral, gitignored.
- `site/stories/<slug>/index.html` — the published scrollytelling artifact
  (self-contained: inline SVG charts, no external JS/CSS dependency, dark-mode
  aware). Open it directly in a browser.
- `site/index.html` — an index of every published story, regenerated from
  `site/manifest.json` on each publish.

`site/` is **git-tracked** (unlike `output/`) — it's the actual GitHub Pages
deploy source. Use separate paths with `--output`/`--site` (or the
`output_root`/`site_root` params on `run_pipeline`) if you want them
somewhere other than the defaults.

### Deploying to GitHub Pages

`.github/workflows/pages.yml` deploys whatever is committed under `site/`
to GitHub Pages on every push to `main` that touches that path (or via
manual `workflow_dispatch`). Pages is already enabled for this repo with
**Source: GitHub Actions**; the live site is
https://menpente.github.io/football-arguments-lab/.

The workflow never runs the pipeline itself — it only publishes what a
human already approved at Gate #2 and a commit already carries. That keeps
"what ships" decided by the editorial gates, not by CI:

```bash
python cli.py run --auto --commit   # or the interactive run, then --commit
git push                            # triggers the Pages deploy
```

Run the tests with:

```bash
python -m unittest discover -s tests -v
```

`tests/test_pipeline_smoke.py` runs the entire pipeline end to end in
scripted mode (approve/refine/reject/kill paths) and checks that publishing
only happens when both gates say yes.

### Tracing (optional, Opik)

The pipeline can emit an [Opik](https://www.comet.com/docs/opik/) trace per
run — one span per stage, plus an `llm`-typed span around every `Reasoner`
call (where a real model goes), with the Gate #1/#2 decisions attached as
metadata. It is **opt-in and off by default**: without it, `opik` is never
imported and the pipeline keeps its "runs offline, only needs Jinja2"
promise.

```bash
pip install -r requirements-tracing.txt

# Option A — local Opik via docker compose (needs Docker running):
./scripts/opik-local.sh up          # downloads Opik's stack into .opik/, starts it
export OPIK_TRACING=1
export OPIK_URL_OVERRIDE=http://localhost:5173/api
python cli.py run --auto            # trace shows at http://localhost:5173
./scripts/opik-local.sh down        # stop it (nuke also drops the data volumes)

# Option B — Opik Cloud:
export OPIK_TRACING=1 OPIK_API_KEY=... OPIK_WORKSPACE=...
python cli.py run --auto
```

`scripts/opik-local.sh` pins Opik's own `docker compose` stack (version in
the script) and runs it under the `opik` profile — this repo doesn't vendor
it. Everything on our side lives in `pipeline/tracing.py`; the stage
functions just carry a `@traced` decorator that is a no-op when
`OPIK_TRACING` is unset.

## What's real vs. mocked in this MVP

Everything runs against **bundled fixture data** so the whole pipeline works
offline with no API keys:

- **Discovery sources** (`data/sources/sample_posts.json`): stand-ins for X,
  Reddit, and news search. `pipeline/discovery.SourceConnector` is the
  interface — swap `JsonFixtureConnector` for a real one (tweepy for X, praw
  for Reddit, a news search API) without touching clustering or scoring.
- **Stats provider** (`data/providers/la_liga_forwards.json`): stands in for
  Opta Analyst, covering the worked example in the spec (Mbappé vs. Raphinha,
  La Liga 2026/27) plus a couple more forwards for extra demo stories.
  `pipeline/data_agent.ProviderConnector` is the
  interface; the "one provider per story" rule (section 9) is enforced by
  construction — a story run takes exactly one connector, so nothing
  downstream can blend sources.
- **Editorial judgement** (pitch framing, question decomposition, scene
  copy): `pipeline/reasoner.Reasoner` is the interface.
  `HeuristicReasoner` is a deterministic, template-based fallback with no
  network calls. To use an actual LLM for sharper framing and prose, wire the
  Claude API into a `Reasoner` implementation (see `claude-api` skill /
  Anthropic docs) and pass it to `run_pipeline(reasoner=...)`.
- **Publishing** (`pipeline/publish_agent.py`): writes the artifact into
  `site/`, the GitHub Pages deploy source, and can optionally stage+commit it
  locally. It never runs `git push` itself — that (and the Pages deploy it
  triggers) is a deliberate, explicit step, kept separate from anything the
  pipeline runs unattended.

## Extending

- **More sources**: implement `SourceConnector.fetch_posts()` for YouTube,
  Threads, Bluesky, forums, or Google Trends and add it to
  `discovery.default_connectors()`.
- **More providers**: implement `ProviderConnector.fetch()` for FotMob,
  FBref, or an official competition feed; respect the priority order in
  `data_agent.DEFAULT_PROVIDER_PRIORITY`.
- **Real clustering/NER**: `discovery.KNOWN_PLAYERS` and
  `discovery.cluster_posts` are a keyword-based MVP clusterer. Swap in an
  embedding-based clustering step without changing `Candidate` or the
  scoring formula.
- **A real Gate #1/#2 UI**: `pipeline/gates.py` currently reads decisions
  from stdin or a scripted dict. The `GateDecision` schema is UI-agnostic —
  a web form or Slack approval flow can produce the same object and hand it
  to `run_pipeline`.

## License

GPL-3.0 — see [LICENSE](LICENSE).
