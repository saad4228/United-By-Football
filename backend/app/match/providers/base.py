from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

import httpx

from app.config import Settings


@dataclass
class TeamRef:
    name: str
    short_name: str | None = None
    tla: str | None = None
    logo_url: str | None = None
    country: str | None = None
    external_id: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None


@dataclass
class CompetitionRef:
    name: str
    code: str | None = None
    country: str | None = None
    logo_url: str | None = None
    priority: int | None = None
    national_teams: bool = False
    espn_league: str | None = None


@dataclass
class NormalizedFixture:
    provider: str
    external_id: str
    home: TeamRef
    away: TeamRef
    competition: CompetitionRef
    kickoff: datetime
    status: str
    score_home: int | None = None
    score_away: int | None = None
    minute: int | None = None
    minute_display: str | None = None
    venue: str | None = None
    referee: str | None = None


class FixtureProvider(ABC):
    """Supplies the match engine with fixtures, scores and live state."""

    key: ClassVar[str]
    name: ClassVar[str]

    @classmethod
    def enabled(cls, settings: Settings) -> bool:
        return True

    @abstractmethod
    async def fetch(self, http: httpx.AsyncClient, now: datetime) -> list[NormalizedFixture]: ...

    def next_interval(self, settings: Settings, has_live: bool) -> int:
        return settings.fixtures_live_interval if has_live else settings.fixtures_idle_interval
