"""Section 14 (Publish Agent): GitHub -> GitHub Pages.

Writes the finished artifact into `site_root`, a directory shaped exactly
like the GitHub Pages source a `.github/workflows/pages.yml` workflow
publishes (see that file): `site/index.html` lists every published story,
and `site/stories/<slug>/index.html` is the story itself. `site_root` is
git-tracked (unlike `output/`, which only holds ephemeral run logs) because
the committed content *is* the deploy artifact — Pages serves whatever is
on the branch.

Actually pushing to GitHub remains a separate, explicit, human-authorized
action — this module never pushes on its own; it reports what it wrote and
(optionally) stages a git commit, leaving `git push` to the operator.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import PublishResult, StorySpec
from .tracing import traced

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _update_index(site_root: Path, story: StorySpec) -> None:
    manifest_path = site_root / "manifest.json"
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
    (site_root / "index.html").write_text(template.render(stories=manifest))


@traced(name="publish_agent")
def publish(story: StorySpec, artifact_path: Path, site_root: Path,
            git_commit: bool = False) -> PublishResult:
    story_dir = site_root / "stories" / story.slug
    story_dir.mkdir(parents=True, exist_ok=True)
    published_path = story_dir / "index.html"
    published_path.write_bytes(artifact_path.read_bytes())
    _update_index(site_root, story)

    if not git_commit:
        return PublishResult(
            status="dry_run",
            slug=story.slug,
            output_path=str(published_path),
            committed=False,
            note="Artifact and site index written locally. Re-run with "
                 "git_commit=True (or `--commit`) to stage+commit them; "
                 "pushing to GitHub (which triggers the Pages deploy "
                 "workflow) remains a separate, explicit step.",
        )

    try:
        subprocess.run(
            ["git", "add", str(published_path), str(site_root / "index.html"),
             str(site_root / "manifest.json")],
            check=True, cwd=site_root.parent,
        )
        commit_message = f"Publish story: {story.title}"
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            check=True, cwd=site_root.parent,
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, cwd=site_root.parent,
            capture_output=True, text=True,
        ).stdout.strip()
        return PublishResult(
            status="published", slug=story.slug, output_path=str(published_path),
            committed=True, commit_sha=sha,
            note="Committed locally. Push to the remote is a separate, "
                 "explicit step, and is what triggers the Pages deploy.",
        )
    except subprocess.CalledProcessError as exc:
        return PublishResult(
            status="blocked", slug=story.slug, output_path=str(published_path),
            committed=False, note=f"git commit failed: {exc}",
        )
