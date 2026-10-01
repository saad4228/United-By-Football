"""Source connector contract.

A connector knows how to talk to one source — a web page, an API, a public app
endpoint, a curated/official feed or user submissions — and returns *normalized*
listings. Everything downstream (match association, redirect resolution,
validation, storage) is shared and connector-agnostic.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

import httpx

from app.config import Settings
from app.database.models import ConnectorType
from app.resolver.ssrf import URLGuard


@dataclass
class DiscoveredLink:
    url: str
    label: str | None = None
    link_type: str = "watch"
    language: str | None = None
    # Quality as *claimed* by the source. Stored, but only shown to users once verified.
    quality: str | None = None
    regions: list[str] | None = None  # ISO codes, "*" worldwide, "!XX" excluded
    access: str | None = None  # free | free_account | licence | subscription
    coverage: str | None = None  # all | selected
    notes: str | None = None
    confirmed: bool | None = None


@dataclass
class DiscoveredMatch:
    home: str
    away: str
    kickoff: datetime | None = None
    competition: str | None = None
    links: list[DiscoveredLink] = field(default_factory=list)
    # Set when the connector already knows our match id (e.g. feeds keyed off our own fixtures).
    match_id: int | None = None


@dataclass(frozen=True)
class KnownMatch:
    id: int
    home: str
    away: str
    kickoff: datetime
    competition_code: str | None
    status: str
    competition_slug: str | None = None
    home_short: str | None = None
    away_short: str | None = None


@dataclass
class ConnectorContext:
    settings: Settings
    http: httpx.AsyncClient
    guard: URLGuard
    now: datetime
    matches: list[KnownMatch]
    log: logging.Logger

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Fetch a source listing through the same SSRF policy used for links."""
        await self.guard.check(url)
        response = await self.http.get(url, follow_redirects=False, **kwargs)
        self.guard.check_peer(response)
        response.raise_for_status()
        return response


class SourceConnector(ABC):
    key: ClassVar[str]
    name: ClassVar[str]
    connector_type: ClassVar[ConnectorType]
    domain: ClassVar[str | None] = None
    description: ClassVar[str] = ""
    # Politeness floor for health checks of this source's links, in seconds.
    min_check_interval: ClassVar[int | None] = None
    # Hard limit for one discovery run.
    timeout: ClassVar[float] = 30.0
    # Phrases that mark a 200 page as dead ("soft 404").
    offline_markers: ClassVar[tuple[str, ...]] = ()
    # Broadcasters' players are often unreachable from outside their country. For such
    # sources a timeout or refused connection means "can't verify from here", not "offline".
    unverifiable_errors: ClassVar[tuple[str, ...]] = ()
    # Final-URL fragments meaning "not available in the checker's region" (e.g. "/unavailable").
    geo_block_url_markers: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def enabled(cls, settings: Settings) -> bool:
        return True

    @abstractmethod
    async def discover(self, ctx: ConnectorContext) -> list[DiscoveredMatch]: ...
