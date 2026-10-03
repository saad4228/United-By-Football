from datetime import timedelta

import httpx
from sqlalchemy import select

from app.database.models import Match, Team, TeamMedia
from app.media.service import MediaService, looks_like_venue, pick_club
from app.utils.time import utcnow

CAMP_NOU_IMAGE = {
    "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Camp_Nou.jpg/1920px-Camp_Nou.jpg?utm_source=x",
    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Camp_Nou.jpg",
    "width": 4000,
    "height": 2250,
    "extmetadata": {
        "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:Someone">Some <b>One</b></a>'},
        "LicenseShortName": {"value": "CC BY-SA 4.0"},
        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"},
    },
}


def club(name, country="Spain", gender="Male", **extra):
    return {"strSport": "Soccer", "strTeam": name, "strCountry": country, "strGender": gender, "idTeam": "133739",
            "intFormedYear": "1899", "strStadium": "Spotify Camp Nou", "intStadiumCapacity": "",
            "strWebsite": "www.fcbarcelona.com", **extra}


def test_pick_club_respects_sport_gender_country_and_name():
    candidates = [
        {**club("Barcelona"), "strSport": "Basketball"},
        club("Barcelona", gender="Female"),
        club("Barcelona SC", country="Ecuador"),
        club("Barcelona"),
    ]
    assert pick_club(candidates, "Barcelona", "Spain", women=False) is candidates[3]
    assert pick_club(candidates, "Barcelona Women", "Spain", women=True) is candidates[1]
    assert pick_club([club("Real Madrid")], "Barcelona", "Spain", women=False) is None
    # A reserve side is never the senior club, even though every word matches.
    assert pick_club([club("Mumbai City FC Reserves", country="India")], "Mumbai City FC", "India", women=False) is None


def test_venue_check_rejects_the_wrong_stadium():
    camp_nou = {"title": "Camp Nou", "description": "Football stadium in Barcelona", "pageimage": "x.jpg"}
    assert looks_like_venue(camp_nou, "Spotify Camp Nou")
    assert not looks_like_venue({**camp_nou, "title": "Wembley Stadium"}, "Spotify Camp Nou")
    assert not looks_like_venue({"title": "Camp Nou", "description": "Album by a band", "pageimage": "x"}, "Camp Nou")
    assert not looks_like_venue({"title": "Camp Nou", "description": "Football stadium"}, "Camp Nou")  # no image


def test_sponsor_named_stadium_ranks_the_right_venue():
    from app.media.service import venue_score
    juve = {"title": "Juventus Stadium", "description": "Football stadium in Turin, Italy", "pageimage": "j.jpg"}
    munich = {"title": "Allianz Arena", "description": "Football stadium in Munich, Germany", "pageimage": "a.jpg"}
    assert venue_score(juve, "Allianz Stadium Turin", "Juventus") > venue_score(munich, "Allianz Stadium Turin", "Juventus")


def wiki_handler(requests: list, image=CAMP_NOU_IMAGE, exact_hit=True):
    def handler(request: httpx.Request):
        params = dict(request.url.params)
        requests.append(params)
        if "thesportsdb.com" in request.url.host:
            return httpx.Response(200, json={"teams": [club("Barcelona")]})
        if params.get("prop") == "imageinfo":
            return httpx.Response(200, json={"query": {"pages": [{"imageinfo": [image]}]}})
        if params.get("generator") == "search":
            return httpx.Response(200, json={"query": {"pages": [
                {"index": 1, "title": "Estadi Johan Cruyff", "description": "Stadium", "pageimage": "jc.jpg"},
                {"index": 2, "title": "Camp Nou", "description": "Football stadium in Barcelona", "pageimage": "cn.jpg"},
            ]}})
        page = {"title": "Camp Nou", "description": "Football stadium in Barcelona, Spain", "pageimage": "Camp_Nou.jpg"}
        return httpx.Response(200, json={"query": {"redirects": [{"from": "Spotify Camp Nou", "to": "Camp Nou"}],
                                                   "pages": [page if exact_hit else {"title": "X", "missing": True}]}})
    return handler


def service(app, handler) -> MediaService:
    svc = MediaService(app.state.db, app.state.settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    svc.sportsdb_limit.interval = svc.wiki_limit.interval = 0
    return svc


async def test_enrich_stores_facts_photo_and_credit(app):
    requests: list = []
    svc = service(app, wiki_handler(requests))
    async with app.state.db.sessions() as session:
        team = await session.scalar(select(Team).where(Team.slug == "barcelona"))
    media = await svc.enrich(team.id)
    assert media.status == "ok"
    assert (media.founded, media.stadium, media.website) == (1899, "Spotify Camp Nou", "https://www.fcbarcelona.com")
    assert media.photo_url.startswith("https://upload.wikimedia.org/") and "?" not in media.photo_url
    assert media.photo_author == "Some One"  # markup stripped
    assert media.photo_license == "CC BY-SA 4.0" and media.photo_page.endswith("File:Camp_Nou.jpg")
    assert all("User-Agent" for _ in requests)


    # Fresh results are reused, not refetched.
    count = len(requests)
    await svc.enrich(team.id)
    assert len(requests) == count


async def test_search_fallback_picks_the_matching_venue(app):
    svc = service(app, wiki_handler([], exact_hit=False))
    photo = await svc.find_photo("Spotify Camp Nou")
    assert photo is not None and photo.subject == "Camp Nou"


async def test_portrait_or_non_free_images_are_rejected(app):
    portrait = {**CAMP_NOU_IMAGE, "width": 1200, "height": 1800}
    assert await service(app, wiki_handler([], image=portrait)).find_photo("Spotify Camp Nou") is None
    non_free = {**CAMP_NOU_IMAGE, "extmetadata": {**CAMP_NOU_IMAGE["extmetadata"],
                                                    "LicenseShortName": {"value": "Fair use"}}}
    assert await service(app, wiki_handler([], image=non_free)).find_photo("Spotify Camp Nou") is None


async def test_home_venue_is_used_when_no_club_facts(app):
    def handler(request: httpx.Request):
        if "thesportsdb.com" in request.url.host:
            return httpx.Response(200, json={"teams": None})
        return wiki_handler([])(request)

    svc = service(app, handler)
    async with app.state.db.sessions() as session:
        match = await session.scalar(select(Match).where(Match.venue.is_not(None)).limit(1))
        team_id, venue = match.home_team_id, match.venue
    media = await svc.enrich(team_id)
    assert media.stadium == venue and media.founded is None


async def test_network_failure_is_retried_later_and_keeps_old_data(app):
    def failing(request):
        raise httpx.ConnectError("offline", request=request)

    async with app.state.db.sessions() as session:
        team = await session.scalar(select(Team).where(Team.slug == "arsenal"))
        session.add(TeamMedia(team_id=team.id, status="ok", stadium="Emirates Stadium",
                              photo_url="https://upload.wikimedia.org/x.jpg", checked_at=utcnow() - timedelta(days=40)))
        await session.commit()
    media = await service(app, failing).enrich(team.id)
    assert media.status == "ok" and media.photo_url == "https://upload.wikimedia.org/x.jpg"


async def test_team_detail_reports_media_state(client):
    detail = (await client.get("/api/teams/barcelona")).json()
    assert detail["slug"] == "barcelona" and detail["media"]["status"] in ("none", "pending")


async def test_missing_country_is_filled_from_club_facts(app):
    svc = service(app, wiki_handler([]))
    async with app.state.db.sessions() as session:
        team = await session.scalar(select(Team).where(Team.slug == "barcelona"))
        team.country = None
        await session.commit()
    await svc.enrich(team.id)
    async with app.state.db.sessions() as session:
        assert (await session.get(Team, team.id)).country == "Spain"


async def test_national_team_name_variants_are_tried(app):
    seen: list[str] = []

    def handler(request: httpx.Request):
        if "thesportsdb.com" in request.url.host:
            seen.append(request.url.params["t"])
            hit = request.url.params["t"] == "Czech Republic"
            return httpx.Response(200, json={"teams": [club("Czech Republic", country="Czech Republic", strStadium="Eden Arena")] if hit else None})
        return wiki_handler([])(request)

    svc = service(app, handler)
    async with app.state.db.sessions() as session:
        team = Team(slug="czechia", name="Czechia")
        session.add(team)
        await session.commit()
    facts = await svc.find_club(team)
    assert seen == ["Czechia", "Czech Republic"] and facts and facts.stadium == "Eden Arena"



async def test_locked_media_is_never_overwritten_or_requeued(app):
    """A hand-picked banner stays exactly as set: no lookup, no refresh, no overwrite."""
    requests: list = []
    svc = service(app, wiki_handler(requests))
    async with app.state.db.sessions() as session:
        team = await session.scalar(select(Team).where(Team.slug == "barcelona"))
        session.add(TeamMedia(
            team_id=team.id, status="ok", locked=True, stadium="My ground",
            photo_url="https://example.org/mine.jpg", photo_author="Me",
            checked_at=utcnow() - timedelta(days=400),  # stale by every refresh rule there is
        ))
        await session.commit()

    assert (await svc.enrich(team.id)).photo_url == "https://example.org/mine.jpg"
    assert (await svc.enrich(team.id, force=True)).photo_url == "https://example.org/mine.jpg"
    assert (await svc.get_or_enrich(team.id)).stadium == "My ground"
    assert requests == [], "a locked row must not be looked up at all"
    assert await svc.next_team() != team.id, "a locked row must not be queued for refresh"
