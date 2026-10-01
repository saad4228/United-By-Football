from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.api.queries import availability, one_click
from app.connectors.api.free_streams.adapter import FreeStream, FreeStreamsConnector, covers, load_registry
from app.connectors.api.free_streams.youtube import YouTubeFinder, team_tokens, title_matches
from app.connectors.base import ConnectorContext, KnownMatch
from app.database.models import LinkStatus, Match, Source, StreamLink
from app.resolver.ssrf import URLGuard
from app.utils.time import utcnow
from app.validator.health import CheckPolicy

KICKOFF = datetime(2026, 10, 4, 19, 0, tzinfo=timezone.utc)


def known(home="Spain", away="Germany", slug="uefa-nations-league", **kw) -> KnownMatch:
    return KnownMatch(id=1, home=home, away=away, kickoff=KICKOFF, competition_code=None, status="scheduled",
                      competition_slug=slug, **kw)


def test_registry_is_valid_and_https_only():
    streams = load_registry()
    assert len(streams) >= 30
    assert all(s.url.startswith("https://") for s in streams)
    assert all(s.coverage in ("all", "selected") for s in streams)
    assert all(s.access in ("free", "free_account", "licence") for s in streams)
    assert all(s.countries for s in streams)


@pytest.mark.parametrize(
    ("regions", "country", "expected"),
    [("BR", "BR", True), ("BR", "IN", False), ("*", "IN", True), ("*,!US", "US", False), ("*,!US", "GB", True),
     ("GB,US", None, None), (None, "IN", None)],
)
def test_availability(regions, country, expected):
    assert availability(regions, country) is expected


def test_national_broadcasters_only_cover_their_own_team():
    rtve = FreeStream(id="rtve", name="RTVE", url="https://x", competitions=("uefa-nations-league",),
                      countries=("ES",), coverage="all", access="free", teams=("Spain",))
    assert covers(rtve, known("Spain", "Germany"))
    assert not covers(rtve, known("Denmark", "Portugal"))
    assert not covers(rtve, known("Spain", "Germany", slug="international-friendly"))


def test_one_click_needs_free_available_and_full_or_confirmed_coverage():
    link = StreamLink(access="free", coverage="all")
    assert one_click(link, True) and one_click(link, None)
    assert not one_click(link, False)
    assert not one_click(StreamLink(access="free", coverage="selected"), True)
    assert one_click(StreamLink(access="free", coverage="selected", confirmed=True), True)
    assert not one_click(StreamLink(access="subscription", coverage="all"), True)


def test_title_matching_needs_both_teams():
    home, away = team_tokens("Barcelona", "Barça"), team_tokens("Real Madrid", "Real Madrid")
    assert title_matches("BARCELONA X REAL MADRID | LALIGA AO VIVO", home, away)
    assert not title_matches("BARCELONA X SEVILLA | AO VIVO", home, away)
    # Generic words alone never identify a team.
    assert "real" not in team_tokens("Real Madrid") and "united" not in team_tokens("Manchester United")


def youtube_handler(calls: list):
    def handler(request: httpx.Request):
        calls.append(request.url.path)
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json={"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUabc"}}}]})
        if request.url.path.endswith("/playlistItems"):
            return httpx.Response(200, json={"items": [{"contentDetails": {"videoId": v}} for v in ("v1", "v2", "v3")]})
        return httpx.Response(200, json={"items": [
            {"id": "v1", "snippet": {"title": "BARCELONA X REAL MADRID - AO VIVO", "liveBroadcastContent": "upcoming"},
             "liveStreamingDetails": {"scheduledStartTime": "2026-10-04T18:55:00Z"}},
            {"id": "v2", "snippet": {"title": "BARCELONA X REAL MADRID (old)", "liveBroadcastContent": "none"}},
            {"id": "v3", "snippet": {"title": "SEVILLA X BETIS", "liveBroadcastContent": "live"},
             "liveStreamingDetails": {"actualStartTime": "2026-10-04T18:00:00Z"}},
        ]})
    return handler


def context(handler, matches=()) -> ConnectorContext:
    async def resolver(host, port):
        return ["142.250.0.1"]

    import logging
    from app.config import Settings
    return ConnectorContext(settings=Settings(youtube_api_key="k"), http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
                            guard=URLGuard(resolver=resolver), now=KICKOFF - timedelta(hours=2), matches=list(matches),
                            log=logging.getLogger("test"))


async def test_youtube_finder_returns_the_matching_scheduled_video_and_caches():
    calls: list = []
    ctx = context(youtube_handler(calls))
    finder = YouTubeFinder("k")
    video = await finder.find(ctx, "@CazeTV", ("Barcelona", "Barça"), ("Real Madrid", None), KICKOFF)
    assert video and video.url == "https://www.youtube.com/watch?v=v1" and video.state == "upcoming"
    assert await finder.find(ctx, "@CazeTV", ("Arsenal", None), ("Chelsea", None), KICKOFF) is None
    assert len(calls) == 3  # second lookup served from cache


async def test_connector_links_confirmed_video_with_api_key():
    match = KnownMatch(id=7, home="Barcelona", away="Real Madrid", kickoff=KICKOFF, competition_code="PD",
                       status="scheduled", competition_slug="la-liga", home_short="Barça")
    ctx = context(youtube_handler([]), [match])
    [listing] = await FreeStreamsConnector().discover(ctx)
    cazetv = next(link for link in listing.links if link.label == "CazéTV")
    assert cazetv.url == "https://www.youtube.com/watch?v=v1" and cazetv.confirmed is True
    assert cazetv.regions == ["BR"] and cazetv.coverage == "all" and cazetv.access == "free"


async def test_sources_are_ordered_for_the_viewers_country(app, client):
    async with app.state.db.sessions() as session:
        match = await session.scalar(select(Match).where(Match.kickoff_time > utcnow()).limit(1))
        source = Source(key="test-free", name="Test free", connector_type="official", enabled=True)
        session.add(source)
        await session.flush()
        for url, regions, access, coverage in [
            ("https://br.example/live", "BR", "free", "all"),
            ("https://in.example/live", "IN", "free", "all"),
            ("https://paid.example/", "*", "subscription", None),
        ]:
            session.add(StreamLink(match_id=match.id, source_id=source.id, original_url=url, url_hash=url,
                                   status=LinkStatus.VALID, regions=regions, access=access, coverage=coverage,
                                   label=url, last_checked_at=utcnow()))
        await session.commit()
        slug = match.slug

    india = (await client.get(f"/api/matches/{slug}/sources", params={"country": "in"})).json()
    ours = [i for i in india["items"] if i["source"]["key"] == "test-free"]
    assert india["country"] == "IN"
    assert ours[0]["label"] == "https://in.example/live" and ours[0]["available"] is True and ours[0]["one_click"]
    assert ours[-1]["label"] == "https://br.example/live" and ours[-1]["available"] is False

    card = (await client.get(f"/api/matches/{slug}", params={"country": "IN"})).json()
    assert card["sources"]["top"]["one_click"] and card["sources"]["top"]["watch_url"].startswith("/api/links/")
    assert (await client.get(f"/api/matches/{slug}/sources", params={"country": "India"})).status_code == 422


def test_unreachable_official_players_are_unverified_not_offline():
    assert "TIMEOUT" in FreeStreamsConnector.unverifiable_errors
    assert CheckPolicy(unverifiable_errors=("TIMEOUT",)).unverifiable_errors == ("TIMEOUT",)
