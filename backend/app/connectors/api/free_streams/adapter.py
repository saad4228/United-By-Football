"""OFFICIAL FREE STREAMS connector: free, legal ways to watch, worldwide.

Reads a researched registry (registry.json) of free official streams (broadcasters' free
players, leagues' own YouTube channels, free-to-air TV) and attaches the ones that cover each
match, with the countries they're available in and their terms (free, free account, TV
licence; every match or selected matches). The API then puts the viewer's own options first.

With UBF_YOUTUBE_API_KEY set, YouTube-based entries link straight to the match's live or
scheduled video when the channel has one, so "Watch" is a single click to the right stream.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from app.connectors.api.free_streams.youtube import YouTubeFinder
from app.connectors.base import ConnectorContext, DiscoveredLink, DiscoveredMatch, KnownMatch, SourceConnector
from app.database.models import ConnectorType
from app.match.normalize import normalize_name

log = logging.getLogger(__name__)
REGISTRY_PATH = Path(__file__).with_name("registry.json")
HORIZON = timedelta(days=7)
ENDED = ("finished", "cancelled", "postponed")


@dataclass(frozen=True)
class FreeStream:
    id: str
    name: str
    url: str
    competitions: tuple[str, ...]
    countries: tuple[str, ...]
    coverage: str
    access: str
    language: str | None = None
    notes: str | None = None
    platform: str | None = None
    youtube_handle: str | None = None
    teams: tuple[str, ...] = field(default_factory=tuple)


def load_registry(path: Path = REGISTRY_PATH) -> list[FreeStream]:
    data = json.loads(path.read_text(encoding="utf-8"))
    streams = []
    for raw in data.get("streams", []):
        if not raw.get("url", "").startswith("https://"):
            log.warning("free stream %s skipped: url must be https", raw.get("id"))
            continue
        streams.append(FreeStream(
            id=raw["id"],
            name=raw["name"],
            url=raw["url"],
            competitions=tuple(raw.get("competitions", [])),
            countries=tuple(raw.get("countries", [])),
            coverage=raw.get("coverage", "selected"),
            access=raw.get("access", "free"),
            language=raw.get("language"),
            notes=raw.get("notes"),
            platform=raw.get("platform"),
            youtube_handle=raw.get("youtube_handle"),
            teams=tuple(raw.get("teams", [])),
        ))
    return streams


def covers(stream: FreeStream, match: KnownMatch) -> bool:
    if match.competition_slug not in stream.competitions:
        return False
    if stream.teams:
        wanted = {normalize_name(t) for t in stream.teams}
        return normalize_name(match.home) in wanted or normalize_name(match.away) in wanted
    return True


class FreeStreamsConnector(SourceConnector):
    key = "free-streams"
    name = "Free official streams"
    connector_type = ConnectorType.OFFICIAL
    description = "Free, legal streams worldwide: broadcasters' free players, league YouTube channels, free-to-air TV."
    min_check_interval = 1800
    # Many of these players refuse connections from outside their own country.
    unverifiable_errors = ("TIMEOUT", "CONNECTION_ERROR")
    geo_block_url_markers = ("/unavailable", "/not-available", "/geo-block", "/geoblock")

    def __init__(self) -> None:
        self._youtube: YouTubeFinder | None = None

    async def discover(self, ctx: ConnectorContext) -> list[DiscoveredMatch]:
        streams = load_registry()
        key = ctx.settings.youtube_api_key
        if key and (self._youtube is None or self._youtube.api_key != key):
            self._youtube = YouTubeFinder(key)
        finder = self._youtube if key else None

        results = []
        for match in ctx.matches:
            if match.status in ENDED or match.kickoff > ctx.now + HORIZON:
                continue
            links = []
            for stream in streams:
                if not covers(stream, match):
                    continue
                url, confirmed, notes = stream.url, None, stream.notes
                if finder and stream.youtube_handle:
                    try:
                        video = await finder.find(ctx, stream.youtube_handle, (match.home, match.home_short),
                                                  (match.away, match.away_short), match.kickoff)
                    except Exception as exc:  # quota, network: fall back to the channel page
                        ctx.log.info("YouTube lookup failed for %s: %s", stream.youtube_handle, exc)
                        video = None
                    if video:
                        url, confirmed = video.url, True
                        notes = f"{'Live now' if video.state == 'live' else 'Scheduled'} on {stream.name}'s YouTube"
                links.append(DiscoveredLink(
                    url=url,
                    label=stream.name,
                    link_type="free",
                    language=stream.language,
                    regions=list(stream.countries),
                    access=stream.access,
                    coverage=stream.coverage,
                    notes=notes,
                    confirmed=confirmed,
                ))
            if links:
                results.append(DiscoveredMatch(home=match.home, away=match.away, kickoff=match.kickoff,
                                               links=links, match_id=match.id))
        return results


CONNECTOR = FreeStreamsConnector
