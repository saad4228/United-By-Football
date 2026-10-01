import httpx
from sqlalchemy import select

from app.database.models import Competition, Match, MatchExternalRef, TeamExternalRef
from app.match.providers.espn_details import (
    ESPNDetails,
    formation_lines,
    parse_events,
    parse_standings,
    parse_stats,
    parse_summary,
)
from app.utils.ics import CalendarEvent, build_calendar
from app.utils.time import utcnow


def player(name, position, place, starter=True, **extra):
    return {"athlete": {"displayName": name}, "position": {"abbreviation": position}, "formationPlace": str(place),
            "starter": starter, "jersey": str(place), **extra}


FULHAM = [player("Keeper", "G", 1), player("Left back", "LB", 3), player("Centre left", "CD-L", 6),
          player("Centre right", "CD-R", 5), player("Right back", "RB", 2), player("Holder left", "LM", 4),
          player("Holder right", "RM", 8), player("Ten", "AM", 10), player("Left ten", "AM-L", 11),
          player("Right ten", "AM-R", 7), player("Nine", "F", 9),
          player("Bench", "SUB", 0, starter=False), player("Came on", "SUB", 0, starter=False, subbedIn=True)]


def summary_payload():
    return {
        "header": {"competitions": [{"competitors": [
            {"homeAway": "home", "team": {"id": "1"}}, {"homeAway": "away", "team": {"id": "2"}}]}]},
        "rosters": [
            {"homeAway": "home", "formation": "4-2-3-1", "roster": FULHAM},
            {"homeAway": "away", "formation": "4-4-2", "roster": FULHAM[:3]},  # incomplete: no lines
        ],
        "keyEvents": [
            {"type": {"type": "yellow-card"}, "team": {"id": "1"}, "clock": {"displayValue": "45'"},
             "participants": [{"athlete": {"displayName": "Left back"}}]},
            {"type": {"type": "halftime"}, "clock": {"displayValue": "45'+1'"}},
            {"type": {"type": "own-goal"}, "scoringPlay": True, "team": {"id": "1"}, "clock": {"displayValue": "63'"},
             "participants": [{"athlete": {"displayName": "Opponent"}}]},
            {"type": {"type": "goal---header"}, "scoringPlay": True, "team": {"id": "2"}, "clock": {"displayValue": "89'"},
             "participants": [{"athlete": {"displayName": "Scorer"}}, {"athlete": {"displayName": "Provider"}}]},
            {"type": {"type": "substitution"}, "team": {"id": "2"}, "clock": {"displayValue": "90'"},
             "participants": [{"athlete": {"displayName": "On"}}, {"athlete": {"displayName": "Off"}}]},
            {"type": {"type": "goal"}, "scoringPlay": True, "team": {"id": "2"}, "period": {"number": 5},
             "participants": [{"athlete": {"displayName": "Shootout kick"}}]},
            {"type": {"type": "start-delay"}, "team": {"id": "1"}},
        ],
        "boxscore": {"teams": [
            {"homeAway": "home", "statistics": [{"name": "possessionPct", "displayValue": "42.7"},
                                                {"name": "accuratePasses", "displayValue": "396"},
                                                {"name": "totalPasses", "displayValue": "451"},
                                                {"name": "passPct", "displayValue": "0.9"}]},
            {"homeAway": "away", "statistics": [{"name": "possessionPct", "displayValue": "57.3"},
                                                {"name": "accuratePasses", "displayValue": "529"},
                                                {"name": "totalPasses", "displayValue": "590"},
                                                {"name": "passPct", "displayValue": "0.9"}]},
        ]},
        "lastFiveGames": [{"team": {"id": "1"}, "events": [
            {"gameResult": "L", "score": "1-0", "atVs": "@", "opponent": {"displayName": "B"}, "gameDate": "2026-09-02T19:00Z"},
            {"gameResult": "W", "score": "3-0", "atVs": "vs", "opponent": {"displayName": "A"}, "gameDate": "2026-08-27T19:00Z"},
        ]}],
        "gameInfo": {"attendance": 24500},
    }


def test_formation_lines_follow_the_formation_and_run_left_to_right():
    starters = [{"name": e["athlete"]["displayName"], "position": e["position"]["abbreviation"],
                 "_place": int(e["formationPlace"])} for e in FULHAM[:11]]
    lines = formation_lines("4-2-3-1", starters)
    assert [[p["name"] for p in line] for line in lines] == [
        ["Keeper"],
        ["Left back", "Centre left", "Centre right", "Right back"],
        ["Holder left", "Holder right"],
        ["Left ten", "Ten", "Right ten"],
        ["Nine"],
    ]
    assert len(formation_lines("4-4-2", starters)) == 4  # any formation that adds up to ten outfielders
    assert formation_lines("4-4-1", starters) is None
    assert formation_lines("4-x-2", starters) is None
    assert formation_lines(None, starters) is None


def test_summary_parses_lineups_events_stats_and_form():
    data = parse_summary(summary_payload())
    # The away side only lists three players: still a line-up, but no pitch layout.
    assert data["lineups"]["home"]["lines"] is not None and data["lineups"]["away"]["lines"] is None
    events = data["events"]
    assert [e["kind"] for e in events] == ["yellow", "period", "own_goal", "goal", "sub"]  # shootout and delays dropped
    halftime, own_goal, goal, sub = events[1], events[2], events[3], events[4]
    assert halftime["label"] == "halftime" and halftime["score"] == "0-0"
    assert own_goal["side"] == "home" and own_goal["score"] == "1-0" and own_goal["assist"] is None
    assert goal["side"] == "away" and goal["assist"] == "Provider" and goal["score"] == "1-1"
    assert (sub["player"], sub["assist"]) == ("On", "Off")
    stats = {s["key"]: (s["home"], s["away"]) for s in data["stats"]}
    assert stats["possession"] == (42.7, 57.3)
    assert stats["pass_accuracy"] == (88, 90)  # from pass counts, not ESPN's rounded 0.9
    assert [g["opponent"] for g in data["form"]["home"]] == ["A", "B"]  # oldest first
    assert data["form"]["home"][1]["home"] is False
    assert data["attendance"] == 24500


def test_full_lineups_and_bench_order():
    payload = summary_payload()
    payload["rosters"][1] = {"homeAway": "away", "formation": "4-2-3-1", "roster": FULHAM}
    lineups = parse_summary(payload)["lineups"]
    home = lineups["home"]
    assert home["formation"] == "4-2-3-1" and len(home["lines"]) == 5
    assert [p["name"] for p in home["subs"]] == ["Came on", "Bench"]
    assert all("_place" not in p for p in home["starters"])


def test_zero_stats_before_kickoff_are_hidden():
    box = {"teams": [{"homeAway": side, "statistics": [{"name": "totalShots", "displayValue": "0"}]}
                     for side in ("home", "away")]}
    assert parse_stats(box, {}) == []


def test_standings_sorting_legend_and_women_ids():
    payload = {
        "season": {"displayName": "2026-27 WSL"},
        "children": [{"name": "2026-27 WSL", "standings": {"entries": [
            {"team": {"id": "9", "displayName": "Second"}, "note": {"description": "Relegation", "color": "##FF7F84"},
             "stats": [{"name": "rank", "value": 2}, {"name": "points", "value": 3}]},
            {"team": {"id": "8", "displayName": "First", "logos": [{"href": "http://a.espncdn.com/x.png"}]},
             "note": {"description": "Champions League", "color": "#81D6AC"},
             "stats": [{"name": "rank", "value": 1}, {"name": "points", "value": 6}, {"name": "pointDifferential", "value": 4}]},
        ]}}],
    }
    table = parse_standings(payload, women=True)
    group = table["groups"][0]
    assert group["name"] is None  # same as the season name
    assert [r["name"] for r in group["rows"]] == ["First", "Second"]
    assert group["rows"][0]["external_id"] == "w8" and group["rows"][0]["logo_url"] == "https://a.espncdn.com/x.png"
    assert table["legend"] == [{"label": "Relegation", "color": "#FF7F84"}, {"label": "Champions League", "color": "#81D6AC"}]
    assert parse_standings({"season": {}})["available"] is False


def test_ics_escapes_folds_and_adds_alarm():
    from datetime import datetime, timezone
    start = datetime(2026, 10, 10, 11, 30, tzinfo=timezone.utc)
    body = build_calendar([CalendarEvent(uid="match-1@ubf", start=start, summary="Brighton & Hove Albion, vs; Spurs",
                                         description="Line one\nLine two " + "x" * 120, alarm_minutes=15)],
                          "Test", start)
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert "SUMMARY:Brighton & Hove Albion\\, vs\\; Spurs" in body
    assert "Line one\\nLine two" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    assert "TRIGGER:-PT15M" in body and "DTEND:20261010T133000Z" in body


async def _first_match(app) -> Match:
    async with app.state.db.sessions() as session:
        return (await session.scalars(select(Match).order_by(Match.kickoff_time))).first()


async def test_internationals_and_team_list_filters(app, client):
    async with app.state.db.sessions() as session:
        comp = (await session.scalars(select(Competition).where(Competition.slug == "mls"))).one()
        comp.national_teams = True
        await session.commit()
    intl = (await client.get("/api/matches", params={"competition": "internationals", "limit": 100})).json()
    assert intl["total"] > 0 and {m["competition"]["slug"] for m in intl["items"]} == {"mls"}
    assert intl["items"][0]["competition"]["national_teams"] is True
    other = (await client.get("/api/matches", params={"competition": "other", "limit": 100})).json()
    assert all(m["competition"]["slug"] != "mls" for m in other["items"])

    match = (await client.get("/api/matches", params={"limit": 1})).json()["items"][0]
    teams = f"{match['home']['slug']},{match['away']['slug']},nonexistent-team"
    mine = (await client.get("/api/matches", params={"teams": teams, "limit": 100})).json()
    slugs = {match["home"]["slug"], match["away"]["slug"]}
    assert mine["total"] > 0 and all({m["home"]["slug"], m["away"]["slug"]} & slugs for m in mine["items"])
    assert (await client.get("/api/matches", params={"teams": "../x,%%"})).json()["total"] == 0
    too_many = ",".join(f"team-{i}" for i in range(31))
    assert (await client.get("/api/matches", params={"teams": too_many})).status_code == 400


async def test_calendar_endpoints(client):
    match = (await client.get("/api/matches", params={"status": "upcoming", "limit": 1})).json()["items"][0]
    r = await client.get(f"/api/matches/{match['slug']}/calendar.ics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "attachment" in r.headers["content-disposition"] and "BEGIN:VALARM" in r.text
    assert f"/match/{match['slug']}" in r.text.replace("\r\n ", "")
    feed = await client.get("/api/calendar/teams.ics", params={"teams": match["home"]["slug"]})
    assert feed.status_code == 200 and feed.text.count("BEGIN:VEVENT") >= 1 and "BEGIN:VALARM" not in feed.text
    assert "content-disposition" not in feed.headers  # subscribable, not a download
    assert (await client.get("/api/calendar/teams.ics", params={"teams": "!!"})).status_code == 400


async def test_details_and_table_are_unavailable_without_espn(client):
    match = (await client.get("/api/matches", params={"limit": 1})).json()["items"][0]
    assert (await client.get(f"/api/matches/{match['slug']}/details")).json() == {
        "available": False, "lineups": None, "events": [], "stats": [], "form": None, "attendance": None}
    assert (await client.get("/api/competitions/premier-league/table")).json()["available"] is False
    assert (await client.get("/api/competitions/nope/table")).status_code == 404


async def test_details_and_table_from_espn(app, client, settings):
    """End to end with ESPN answered by a stub: event ids and league slugs map onto our data."""
    seen = []

    def espn(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        if request.url.path.endswith("/all/summary"):
            return httpx.Response(200, json=summary_payload())
        if request.url.path.endswith("/eng.1/standings"):
            return httpx.Response(200, json={"season": {"displayName": "2026-27"}, "children": [
                {"name": "2026-27", "standings": {"entries": [
                    {"team": {"id": "359", "displayName": "Arsenal"}, "stats": [{"name": "rank", "value": 1}]},
                    {"team": {"id": "000", "displayName": "Unknown FC"}, "stats": [{"name": "rank", "value": 2}]},
                ]}}]})
        return httpx.Response(404)

    engine = app.state.engine
    engine.details = ESPNDetails(httpx.AsyncClient(transport=httpx.MockTransport(espn)))
    settings.demo_mode, settings.espn_enabled = False, True
    match = await _first_match(app)
    async with app.state.db.sessions() as session:
        session.add(MatchExternalRef(match_id=match.id, provider="espn", external_id="401878777"))
        comp = (await session.scalars(select(Competition).where(Competition.slug == "premier-league"))).one()
        comp.espn_league = "eng.1"
        session.add(TeamExternalRef(team_id=match.home_team_id, provider="espn", external_id="359"))
        await session.commit()

    details = (await client.get(f"/api/matches/{match.slug}/details")).json()
    assert details["available"] is True and len(details["events"]) == 5 and details["attendance"] == 24500
    await client.get(f"/api/matches/{match.slug}/details")
    assert sum(1 for u in seen if u.path.endswith("/summary")) == 1  # cached
    assert seen[0].params["event"] == "401878777"

    table = (await client.get("/api/competitions/premier-league/table")).json()
    rows = table["groups"][0]["rows"]
    assert table["available"] and table["groups"][0]["name"] is None
    assert rows[0]["team"]["id"] == match.home_team_id and rows[1]["team"] is None
    assert (await client.get("/api/competitions/la-liga/table")).json()["available"] is False  # no league slug yet
