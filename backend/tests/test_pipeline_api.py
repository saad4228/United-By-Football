from datetime import timedelta

from sqlalchemy import select

from app.connectors.api.demo_feed.adapter import parse_events
from app.connectors.base import ConnectorContext, SourceConnector
from app.connectors.registry import sync_sources
from app.connectors.web.demo_listing.adapter import parse_listing, split_title
from app.database.models import ConnectorType, CrawlRun, LinkStatus, Match, StreamLink
from app.utils.time import utcnow


def test_split_title_handles_common_separators():
    assert split_title("Man City v Arsenal") == ("Man City", "Arsenal")
    assert split_title("Barça vs. Real Madrid") == ("Barça", "Real Madrid")
    assert split_title("Inter - Milan") == ("Inter", "Milan")
    assert split_title("Just a headline") is None


def test_web_listing_parser_sanitizes_and_extracts_links():
    html = """
    <div class="event-row"><span class="league">EPL</span><time datetime="2026-10-01T19:00:00+00:00">19:00</time>
      <h3 class="event-title">Man City <b>v</b> Arsenal<script>alert(1)</script></h3>
      <a class="stream-link" href="https://a.example/1" data-lang="English">Channel 1</a>
      <a class="stream-link" href="https://a.example/2">Channel <i>2</i></a>
    </div>
    <div class="event-row"><h3 class="event-title">No separator here</h3></div>
    """
    [listing] = parse_listing(html)
    assert (listing.home, listing.away) == ("Man City", "Arsenal")
    assert listing.kickoff.hour == 19 and listing.competition == "EPL"
    assert [link.url for link in listing.links] == ["https://a.example/1", "https://a.example/2"]
    assert listing.links[1].label == "Channel 2"


def test_api_feed_parser_skips_garbage():
    payload = {"events": [
        {"home": "MCI", "away": "ARS", "start": "2026-10-01T19:00:00+00:00", "streams": [{"url": "https://x/1"}, "bad"]},
        {"home": "", "away": "ARS"},
        {"home": "LIV", "away": "CHE", "start": "not-a-date", "streams": []},
    ]}
    events = parse_events(payload)
    assert [(e.home, e.away) for e in events] == [("MCI", "ARS"), ("LIV", "CHE")]
    assert events[1].kickoff is None and len(events[0].links) == 1


class ExplodingConnector(SourceConnector):
    key = "exploding"
    name = "Exploding"
    connector_type = ConnectorType.WEB

    async def discover(self, ctx: ConnectorContext):
        raise ValueError("layout changed")


async def test_full_pipeline_and_isolation(app, client, admin_headers):
    engine = app.state.engine
    broken = ExplodingConnector()
    engine.connectors.append(broken)
    async with app.state.db.sessions() as session:
        await sync_sources(session, engine.connectors)

    results = {r["source"]: r for r in await engine.run_sources()}
    assert results["exploding"]["status"] == "error"
    assert results["exploding"]["error_code"] == "PARSER_ERROR"
    for key in ("demo-stream-guide", "demo-event-feed", "official-broadcasters"):
        assert results[key]["status"] == "ok", results[key]
        assert results[key]["matched"] > 0
    # The fictional fixture on the demo listing is reported, never invented.
    assert results["demo-stream-guide"]["unmatched"] == 1

    async with app.state.db.sessions() as session:
        statuses = set((await session.scalars(select(StreamLink.status))).all())
        failed = await session.scalar(select(CrawlRun).where(CrawlRun.connector_key == "exploding"))
    assert failed.status == "error" and "layout changed" in failed.error
    assert LinkStatus.VALID in statuses and LinkStatus.DISCOVERED not in statuses

    # Live match pages expose sources with health states and a click-through URL.
    live = (await client.get("/api/matches/live")).json()
    candidates = live + (await client.get("/api/matches?status=upcoming&limit=100")).json()["items"]
    with_sources = next(m for m in candidates if m["sources"]["working"])
    assert with_sources["sources"]["top"]["label"]  # cards name the best working source
    payload = (await client.get(f"/api/matches/{with_sources['slug']}/sources")).json()
    assert payload["items"], payload
    healths = [i["health"] for i in payload["items"]]
    assert healths == sorted(healths, key=["working", "checking", "unverified", "offline"].index)
    working = next(i for i in payload["items"] if i["health"] == "working")
    assert working["last_checked_at"] and working["watch_url"]
    assert all(i["quality"] is None for i in payload["items"])  # never verified for HTML pages
    for item in payload["items"]:
        if item["health"] == "offline":
            assert item["watch_url"] is None and item["message"]

    go = await client.get(working["watch_url"], follow_redirects=False)
    assert go.status_code == 302 and go.headers["location"].startswith(("http://", "https://"))

    overview = (await client.get("/api/admin/overview", headers=admin_headers)).json()
    assert overview["links"]["working"] > 0 and overview["clicks_24h"]["total"] == 1


async def test_links_missing_from_next_crawl_expire_but_empty_results_do_not_wipe(app):
    engine = app.state.engine
    feed = next(c for c in engine.connectors if c.key == "demo-event-feed")
    first = (await engine.run_sources([feed.key]))[0]
    assert first["matched"] > 1
    original = feed.discover

    async def only_first(ctx):
        return (await original(ctx))[:1]

    feed.discover = only_first
    second = (await engine.run_sources([feed.key]))[0]
    assert second["status"] == "ok" and second["expired"] > 0

    async def nothing(ctx):
        return []

    feed.discover = nothing
    third = (await engine.run_sources([feed.key]))[0]
    # An empty result looks like a broken parser: keep existing links, flag the run.
    assert third["status"] == "error" and third["expired"] == 0


async def test_home_and_filters(client):
    home = (await client.get("/api/home")).json()
    assert home["featured"]["mode"] in ("live", "next", "always_on")
    assert home["demo_mode"] is True and len(home["competitions"]) == 8

    page = (await client.get("/api/matches", params={"status": "upcoming", "competition": "premier-league"})).json()
    assert page["items"] and all(m["competition"]["slug"] == "premier-league" for m in page["items"])
    assert all(m["status"] == "scheduled" for m in page["items"])

    team = (await client.get("/api/matches", params={"team": "arsenal"})).json()
    assert all("arsenal" in (m["home"]["slug"], m["away"]["slug"]) for m in team["items"])

    now = utcnow()
    window = (await client.get("/api/matches", params={
        "date_from": now.isoformat(), "date_to": (now + timedelta(hours=6)).isoformat()})).json()
    assert window["total"] > 0


async def test_search_finds_teams_by_alias(client):
    result = (await client.get("/api/search", params={"q": "spurs"})).json()
    assert result["teams"][0]["slug"] == "tottenham-hotspur"
    assert all("tottenham-hotspur" in (m["home"]["slug"], m["away"]["slug"]) for m in result["matches"])
    empty = (await client.get("/api/search", params={"q": "%_"})).json()
    assert empty["teams"] == []


async def test_match_detail_by_slug_and_id(app, client):
    async with app.state.db.sessions() as session:
        match = await session.scalar(select(Match).limit(1))
    by_id = (await client.get(f"/api/matches/{match.id}")).json()
    by_slug = (await client.get(f"/api/matches/{match.slug}")).json()
    assert by_id["id"] == by_slug["id"] == match.id
    assert (await client.get("/api/matches/does-not-exist")).status_code == 404


async def test_admin_requires_token(client, admin_headers):
    assert (await client.get("/api/admin/overview")).status_code == 401
    assert (await client.get("/api/admin/overview", headers={"X-Admin-Token": "nope"})).status_code == 401
    assert (await client.post("/api/sources/run")).status_code == 401
    assert (await client.get("/api/admin/sources", headers=admin_headers)).status_code == 200


async def test_search_is_rate_limited(app, client):
    app.state.settings.rate_limit_search = 3
    codes = [(await client.get("/api/search", params={"q": "arsenal"})).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[-1] == 429
