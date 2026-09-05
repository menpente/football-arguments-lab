"""Section 9: Data/Research Agent.

Fetches one provider's stats for the players a story needs. The "one
provider per story" rule (section 9) is enforced by construction: a story
run picks a single `ProviderConnector` and every player is fetched through
it, so nothing downstream can silently blend sources.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from .models import Dataset, ResearchBrief
from .tracing import traced

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Priority order from section 9; used when choosing among available connectors.
DEFAULT_PROVIDER_PRIORITY = ["Opta Analyst", "official competition feed", "FotMob", "FBref"]


class ProviderConnector(ABC):
    """One stats provider. Real implementations call the provider's API;
    this MVP ships a fixture-backed connector for Opta Analyst.
    """

    provider_name: str

    @abstractmethod
    def fetch(self, players: list[str], competition: str, season: str) -> Dataset:
        ...


class JsonFixtureProviderConnector(ProviderConnector):
    def __init__(self, provider_name: str, fixture_path: Path):
        self.provider_name = provider_name
        self.fixture_path = fixture_path

    def fetch(self, players: list[str], competition: str, season: str) -> Dataset:
        raw = json.loads(self.fixture_path.read_text())
        available = raw["players"]
        missing = [p for p in players if p not in available]
        if missing:
            raise LookupError(
                f"{self.provider_name} fixture has no data for: {', '.join(missing)}"
            )
        selected = {p: available[p] for p in players}
        return Dataset(
            provider=raw["provider"],
            competition=raw["competition"],
            season=raw["season"],
            captured_at=raw["captured_at"],
            source_url=raw["source_url"],
            data={"players": selected},
        )


def default_connector() -> ProviderConnector:
    return JsonFixtureProviderConnector(
        "Opta Analyst", DATA_DIR / "providers" / "la_liga_forwards.json"
    )


@traced(name="data_agent")
def fetch_dataset(brief: ResearchBrief, subject: str, connector: ProviderConnector | None = None,
                   competition: str = "La Liga", season: str = "2026/27") -> Dataset:
    connector = connector or default_connector()
    players = [subject, *brief.comparison_candidates]
    return connector.fetch(players, competition, season)
