from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select

from app.database.models import Match, Source
from app.match.providers.base import CompetitionRef, NormalizedFixture, TeamRef
from app.match.providers.espn import LEAGUES, ESPNProvider, League, map_status, parse_scoreboard
from app.match.sync import FixtureSyncer, sync_provider
from app.match.teams import TeamDirectory
from app.scheduler.engine import purge_demo_data

NOW = datetime(2026, 10, 1, 19, 30, tzinfo=timezone.utc)


def competitor(side, team_id, name, short, abbr, score="0", color="d02a3e"):
    return {
        "homeAway": side,
        "score": score,
        "team": {"id": team_id, "displayName": name, "shortDisplayName": short, "abbreviation": abbr,
                 "color": color, "alternateColor": "ffffff", "logo": f"https://a.espncdn.com/{team_id}.png"},
    }


def event(event_id, date, state, name, home, away, clock=0.0, display="0'", short="Scheduled"):
    return {
        "id": event_id,
        "date": date,
        "competitions": [{
            "venue": {"fullName": "Parken"},
            "status": {"clock": clock, "displayClock": display,
                       "type": {"state": state, "name": name, "shortDetail": short}},
            "competitors": [home, away],
        }],
    }


def payload(*events, calendar_type="list", calendar=None, name="UEFA Nations League"):
    return {
        "leagues": [{"name": name, "calendarType": calendar_type, "calendar": calendar or [],
                     "logos": [{"href": "http://a.espncdn.com/lg-dark.png", "rel": ["full", "dark"]},
                               {"href": "http://a.espncdn.com/lg.png", "rel": ["full", "default"]}]}],
        "events": list(events),
    }


DEN = competitor("home", "474", "Denmark", "Denmark", "DEN", "2")
POR = competitor("away", "482", "Portugal", "Portugal", "POR", "1", "006600")


def test_status_mapping():
    assert map_status({"clock": 4140, "displayClock": "69'", "type": {"state": "in", "name": "STATUS_SECOND_HALF"}}) == ("live", 69, "69'")
    assert map_status({"type": {"state": "in", "name": "STATUS_HALFTIME"}}) == ("halftime", 45, "HT")
    assert map_status({"type": {"state": "post", "name": "STATUS_FULL_TIME", "shortDetail": "FT"}})[0] == "finished"
    assert map_status({"type": {"state": "post", "name": "STATUS_FINAL_PEN", "shortDetail": "FT-Pens"}})[2] == "FT-Pens"
    assert map_status({"type": {"state": "pre", "name": "STATUS_POSTPONED"}})[0] == "postponed"
    assert map_status({"type": {"state": "pre", "name": "STATUS_SCHEDULED"}}) == ("scheduled", None, None)


def test_parse_scoreboard_live_event():
    data = payload(event("1", "2026-10-01T18:45Z", "in", "STATUS_SECOND_HALF", DEN, POR, 3960, "66'", "66'"))
    [f] = parse_scoreboard(data, "uefa.nations", LEAGUES["uefa.nations"])
    assert (f.home.name, f.away.name, f.score_home, f.score_away) == ("Denmark", "Portugal", 2, 1)
    assert (f.status, f.minute, f.minute_display, f.venue) == ("live", 66, "66'", "Parken")
    assert f.home.primary_color == "#D02A3E" and f.home.external_id == "474"
    assert f.competition.priority == LEAGUES["uefa.nations"].priority
    assert f.competition.logo_url == "https://a.espncdn.com/lg.png"  # light variant, upgraded to https
    assert f.kickoff == datetime(2026, 10, 1, 18, 45, tzinfo=timezone.utc)


def test_scheduled_events_have_no_score_and_bad_events_are_skipped():
    data = payload(
        event("2", "2026-10-03T12:30Z", "pre", "STATUS_SCHEDULED", DEN, POR),
        {"id": "3", "date": "not-a-date", "competitions": [{"competitors": [DEN, POR]}]},
        {"id": "4", "date": "2026-10-03T12:30Z", "competitions": [{"competitors": [DEN]}]},
    )
    [f] = parse_scoreboard(data, "uefa.nations", LEAGUES["uefa.nations"])
    assert f.status == "scheduled" and f.score_home is None and f.score_away is None


def test_womens_teams_are_kept_apart_from_the_mens_club():
    home = competitor("home", "20061", "Manchester United", "Man Utd", "MAN")
    away = competitor("away", "20062", "Liverpool", "Liverpool", "LIV")
    [f] = parse_scoreboard(payload(event("5", "2026-10-03T12:30Z", "pre", "STATUS_SCHEDULED", home, away)),
                           "eng.w.1", LEAGUES["eng.w.1"])
    assert f.home.name == "Manchester United Women" and f.home.short_name == "Man Utd Women"


async def test_provider_only_fetches_match_days_and_respects_cache():
    calls: list[str] = []
    league_calendar = ["2026-10-01T07:00Z", "2026-10-04T07:00Z", "2026-12-01T07:00Z"]

    def handler(request: httpx.Request):
        dates = request.url.params.get("dates")
        calls.append(f"{request.url.path.split('/')[-2]}:{dates}")
        if request.url.path.endswith("/eng.1/scoreboard"):
            ev = [event("10", "2026-10-01T19:00Z", "in", "STATUS_FIRST_HALF", DEN, POR, 1800, "30'")] if dates == "20261001" else []
            return httpx.Response(200, json=payload(*ev, calendar_type="day", calendar=league_calendar, name="EPL"))
        return httpx.Response(200, json=payload())

    provider = ESPNProvider({"eng.1": League("PL", "England", 95)})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        fixtures = await provider.fetch(http, NOW)
        first = list(calls)
        calls.clear()
        await provider.fetch(http, NOW)

    # Calendar + only the two match days inside the window (not every day, not December).
    assert first == ["eng.1:None", "eng.1:20261001", "eng.1:20261004"]
    assert [f.status for f in fixtures] == ["live"]
    # Immediately polling again fetches nothing: every page is still fresh.
    assert calls == []


async def test_live_page_is_refetched_quickly(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("app.match.providers.espn.time.monotonic", lambda: clock[0])
    calls: list[str] = []

    def handler(request):
        dates = request.url.params.get("dates")
        calls.append(str(dates))
        ev = [event("10", "2026-10-01T19:00Z", "in", "STATUS_FIRST_HALF", DEN, POR, 1800, "30'")] if dates == "20261001" else []
        return httpx.Response(200, json=payload(*ev, calendar_type="day", calendar=["2026-10-01T07:00Z", "2026-10-04T07:00Z"]))

    provider = ESPNProvider({"eng.1": League("PL", "England", 95)})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await provider.fetch(http, NOW)
        calls.clear()
        clock[0] += 31
        await provider.fetch(http, NOW)
    assert calls == ["20261001"]  # only the day with the live match


async def test_provider_failure_is_reported(app):
    def handler(request):
        return httpx.Response(503)

    provider = ESPNProvider({"eng.1": League("PL", "England", 95)})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await sync_provider(app.state.db, provider, http)
    assert result["status"] == "error"


async def test_espn_names_resolve_to_seeded_clubs_and_ids_stick(app):
    def fixture(ext, home, away, home_id, away_id, country="England"):
        return NormalizedFixture(
            provider="espn", external_id=ext,
            home=TeamRef(home, external_id=home_id, country=country, primary_color="#EF0107"),
            away=TeamRef(away, external_id=away_id, country=country),
            competition=CompetitionRef("English Premier League", "PL", "England", priority=95),
            kickoff=NOW + timedelta(days=2), status="scheduled")

    async with app.state.db.sessions() as session:
        directory = await TeamDirectory.load(session)
        syncer = FixtureSyncer(session, directory, "espn")
        fixtures = [fixture("e1", "Arsenal", "Leeds United", "359", "357")]
        await syncer.prepare(fixtures)
        match = await syncer.upsert(fixtures[0])
        await session.commit()
        await session.refresh(match, ["home_team", "away_team"])
        assert match.home_team.slug == "arsenal"  # seeded club, seeded crest kept
        assert match.home_team.primary_color == "#EF0107"
        assert match.away_team.name == "Leeds United"  # new club created from the feed

        # Renamed in the feed later: the provider id still finds the same club.
        directory = await TeamDirectory.load(session)
        renamed = await directory.resolve_or_create(session, TeamRef("Leeds Utd FC", external_id="357"), "espn")
        assert renamed.id == match.away_team_id

        # Same name, different country, different id: a different club.
        other = await directory.resolve_or_create(session, TeamRef("Arsenal", external_id="999", country="Argentina"), "espn")
        assert other.id != match.home_team_id


async def test_same_provider_events_between_same_clubs_stay_separate(app):
    def fixture(ext, hours):
        return NormalizedFixture(provider="espn", external_id=ext, home=TeamRef("Barcelona"), away=TeamRef("Real Madrid"),
                                 competition=CompetitionRef("La Liga", "PD"), kickoff=NOW + timedelta(hours=hours),
                                 status="scheduled")

    async with app.state.db.sessions() as session:
        directory = await TeamDirectory.load(session)
        fixtures = [fixture("league", 30), fixture("cup", 50)]
        syncer = FixtureSyncer(session, directory, "espn")
        await syncer.prepare(fixtures)
        a = await syncer.upsert(fixtures[0])
        b = await syncer.upsert(fixtures[1])
        await session.commit()
        assert a.id != b.id


async def test_switching_off_demo_mode_purges_demo_data(app):
    async with app.state.db.sessions() as session:
        before = await session.scalar(select(func.count(Match.id)))
        assert before > 0
        assert await session.scalar(select(func.count(Source.id)).where(Source.key == "demo-stream-guide")) == 1
    removed = await purge_demo_data(app.state.db)
    async with app.state.db.sessions() as session:
        assert removed == before
        assert await session.scalar(select(func.count(Match.id))) == 0
        assert await session.scalar(select(func.count(Source.id)).where(Source.key.like("demo-%"))) == 0
