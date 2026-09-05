"""Section 12 (Artifact Agent): renders a StorySpec into the interactive
scrollytelling HTML artifact. This is the only place that produces markup —
every other agent works with plain data.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .charts import render_bar_chart_svg
from .models import StorySpec
from .tracing import traced

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_artifact(story: StorySpec) -> str:
    template = _env.get_template("scrollytelling.html.j2")

    class _SceneView:
        def __init__(self, scene):
            self.id = scene.id
            self.kind = scene.kind
            self.headline = scene.headline
            self.body = scene.body
            self.chart = scene.chart
            self.chart_svg = render_bar_chart_svg(scene.chart) if scene.chart else ""

    class _StoryView:
        def __init__(self, story: StorySpec):
            self.title = story.title
            self.dek = story.dek
            self.scenes = [_SceneView(s) for s in story.scenes]
            self.data_sources = story.data_sources

    return template.render(story=_StoryView(story))


@traced(name="artifact_agent")
def write_artifact(story: StorySpec, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    html = render_artifact(story)
    path = output_dir / "index.html"
    path.write_text(html)
    return path
