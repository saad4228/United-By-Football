"""Find the exact YouTube live video for a match on an official channel.

Uses the official YouTube Data API v3 (needs UBF_YOUTUBE_API_KEY). Per channel and refresh it
costs 3 quota units (channel → uploads playlist → video details), well inside the free daily
quota. Without a key the connector links to the channel's streams page instead.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.connectors.base import ConnectorContext
from app.match.normalize import normalize_name

API = "https://www.googleapis.com/youtube/v3"
CACHE_SECONDS = 600
START_TOLERANCE = timedelta(hours=3)
# Words too common in club names to identify a team on their own.
GENERIC = {"united", "city", "real", "club", "sporting", "athletic", "atletico", "deportivo", "women", "town",
           "county", "rovers", "wanderers", "albion", "hotspur", "olympique", "racing", "inter", "saint"}


@dataclass(frozen=True)
class LiveVideo:
    video_id: str
    title: str
    starts: datetime | None
    state: str  # live | upcoming

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def team_tokens(*names: str | None) -> set[str]:
    tokens: set[str] = set()
    for name in names:
        if name:
            tokens |= {t for t in normalize_name(name).split() if len(t) >= 3 and t not in GENERIC}
    return tokens


def title_matches(title: str, home: set[str], away: set[str]) -> bool:
    words = set(normalize_name(title).split())
    return bool(home & words) and bool(away & words)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class YouTubeFinder:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._uploads: dict[str, str] = {}
        self._videos: dict[str, tuple[float, list[LiveVideo]]] = {}

    async def _api(self, ctx: ConnectorContext, path: str, **params) -> dict:
        response = await ctx.get(f"{API}/{path}", params={**params, "key": self.api_key}, timeout=15)
        return response.json()

    async def live_and_upcoming(self, ctx: ConnectorContext, handle: str) -> list[LiveVideo]:
        cached = self._videos.get(handle)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        if handle not in self._uploads:
            data = await self._api(ctx, "channels", part="contentDetails", forHandle=handle)
            items = data.get("items") or []
            if not items:
                self._videos[handle] = (time.monotonic(), [])
                return []
            self._uploads[handle] = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        playlist = await self._api(ctx, "playlistItems", part="contentDetails", playlistId=self._uploads[handle],
                                   maxResults=50)
        ids = [i["contentDetails"]["videoId"] for i in playlist.get("items", []) if i.get("contentDetails")]
        videos: list[LiveVideo] = []
        if ids:
            details = await self._api(ctx, "videos", part="snippet,liveStreamingDetails", id=",".join(ids))
            for item in details.get("items", []):
                state = (item.get("snippet") or {}).get("liveBroadcastContent")
                if state not in ("live", "upcoming"):
                    continue
                live = item.get("liveStreamingDetails") or {}
                videos.append(LiveVideo(
                    video_id=item["id"],
                    title=(item.get("snippet") or {}).get("title", ""),
                    starts=_parse_time(live.get("actualStartTime") or live.get("scheduledStartTime")),
                    state=state,
                ))
        self._videos[handle] = (time.monotonic(), videos)
        return videos

    async def find(self, ctx: ConnectorContext, handle: str, home: tuple[str | None, ...], away: tuple[str | None, ...],
                   kickoff: datetime) -> LiveVideo | None:
        home_tokens, away_tokens = team_tokens(*home), team_tokens(*away)
        if not home_tokens or not away_tokens:
            return None
        for video in await self.live_and_upcoming(ctx, handle):
            if video.starts and abs(video.starts - kickoff) > START_TOLERANCE:
                continue
            if title_matches(video.title, home_tokens, away_tokens):
                return video
        return None
