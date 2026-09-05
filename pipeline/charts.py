"""Minimal inline-SVG bar chart renderer.

The artifact is meant to be a self-contained static file deployable as-is
(section 12, GitHub -> Vercel), so charts are rendered as inline SVG rather
than pulled from a JS charting CDN — no runtime dependency, nothing to
break if a script fails to load.
"""
from __future__ import annotations

from .models import ChartSpec

WIDTH = 480
HEIGHT = 240
PADDING = 32
BAR_COLORS = ["#2563eb", "#dc2626", "#059669", "#7c3aed"]


def render_bar_chart_svg(chart: ChartSpec) -> str:
    values = [s["value"] for s in chart.series]
    max_value = max(values) if values else 1
    max_value = max_value * 1.15 if max_value else 1

    n = len(chart.series)
    plot_width = WIDTH - 2 * PADDING
    plot_height = HEIGHT - 2 * PADDING
    bar_width = plot_width / (n * 1.6)
    gap = (plot_width - bar_width * n) / max(n - 1, 1) if n > 1 else 0

    bars = []
    for i, item in enumerate(chart.series):
        value = item["value"]
        bar_height = (value / max_value) * plot_height if max_value else 0
        x = PADDING + i * (bar_width + gap)
        y = HEIGHT - PADDING - bar_height
        color = BAR_COLORS[i % len(BAR_COLORS)]
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
            f'height="{bar_height:.1f}" fill="{color}" rx="4"/>'
            f'<text x="{x + bar_width / 2:.1f}" y="{y - 8:.1f}" '
            f'text-anchor="middle" class="chart-value">{value}{chart.unit}</text>'
            f'<text x="{x + bar_width / 2:.1f}" y="{HEIGHT - PADDING + 18:.1f}" '
            f'text-anchor="middle" class="chart-label">{item["label"]}</text>'
        )

    axis = (
        f'<line x1="{PADDING}" y1="{HEIGHT - PADDING}" x2="{WIDTH - PADDING}" '
        f'y2="{HEIGHT - PADDING}" class="chart-axis"/>'
    )

    return (
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" class="chart" role="img" '
        f'aria-label="{chart.title}">'
        f'<text x="{WIDTH / 2}" y="18" text-anchor="middle" class="chart-title">'
        f'{chart.title}</text>'
        f"{axis}{''.join(bars)}"
        f"</svg>"
    )
