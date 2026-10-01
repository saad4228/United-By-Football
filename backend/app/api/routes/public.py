import re
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app import __version__
from app.api.deps import get_engine, get_session, get_settings_dep, rate_limit
from app.api.queries import (
    ACCESS_RANK,
    HEALTH_OF_STATUS,
    availability,
    one_click,
    competition_out,
    error_message,
    importance,
    list_matches,
    match_out,
    match_select,
    matches_out,
    source_reliability,
    source_summaries,
    team_out,
)
from app.api.schemas import (
    CompetitionOut,
    CompetitionWithCounts,
    Featured,
    HomeOut,
    MatchDetailsOut,
    MatchOut,
    MatchPage,
    MatchSources,
    MetaOut,
    SearchOut,
    SourceInfo,
    SourceLinkOut,
    PhotoOut,
    SourceSummary,
    TableGroup,
    TableOut,
    TableRow,
    TeamDetailOut,
    TeamMediaOut,
    TeamOut,
)
from app.config import Settings
from app.scheduler.engine import Engine
from app.database.models import (
    LIVE_STATUSES,
    Competition,
    LinkClick,
    LinkStatus,
    Match,
    MatchExternalRef,
    MatchStatus,
    StreamLink,
    Team,
    TeamAlias,
    TeamExternalRef,
)
from app.match.normalize import normalize_name
from app.utils.ics import CalendarEvent, build_calendar
from app.utils.time import utcnow

router = APIRouter(prefix="/api")


def viewer_country(request: Request, country: str | None = Query(None, pattern="^[A-Za-z]{2}$")) -> str | None:
    """The viewer's country: chosen in the UI (?country=), else a CDN header such as
    Cloudflare's CF-IPCountry in production. Only used to order and filter sources."""
    if country:
        return country.upper()
    header = request.headers.get("cf-ipcountry") or request.headers.get("x-country-code")
    return header.upper() if header and len(header) == 2 and header.isalpha() else None
StatusFilter = Literal["live", "upcoming", "finished", "all"]
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
MAX_TEAMS = 30


def team_slugs(raw: str | None) -> list[str] | None:
    """A comma-separated list of team slugs (from "My teams"), validated and de-duplicated."""
    if not raw:
        return None
    slugs = list(dict.fromkeys(s.strip().lower() for s in raw.split(",") if SLUG.match(s.strip().lower())))
    if len(slugs) > MAX_TEAMS:
        raise HTTPException(400, f"At most {MAX_TEAMS} teams")
    return slugs or None
HEALTH_ORDER = {"working": 0, "checking": 1, "unverified": 2, "offline": 3}


@router.get("/meta", response_model=MetaOut)
async def meta(settings: Settings = Depends(get_settings_dep)) -> MetaOut:
    return MetaOut(
        name="United By Football",
        version=__version__,
        demo_mode=settings.demo_mode,
        server_time=utcnow(),
        refresh_seconds={"live": 12, "upcoming": 45, "sources": 10},
    )


@router.get("/home", response_model=HomeOut, dependencies=[rate_limit("matches")])
async def home(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    country: str | None = Depends(viewer_country),
) -> HomeOut:
    now = utcnow()
    live, _ = await list_matches(session, status="live", limit=40)
    upcoming, _ = await list_matches(session, status="upcoming", date_from=now - timedelta(minutes=10),
                                     date_to=now + timedelta(hours=36), limit=80)
    featured_match, mode = None, "always_on"
    if live:
        featured_match, mode = live[0], "live"
    else:
        # Big fixtures only: the seeded leagues plus e.g. the Nations League during international breaks.
        major_soon = [m for m in upcoming if m.competition and m.competition.priority >= 60]
        if major_soon:
            def score(m: Match) -> float:
                hours = max((m.kickoff_time - now).total_seconds() / 3600, 0)
                return importance(m) - hours * 2.5
            featured_match, mode = max(major_soon, key=score), "next"

    next_matches = [m for m in upcoming if m is not featured_match][:3]
    shown = live + next_matches + ([featured_match] if featured_match else [])
    summaries = await source_summaries(session, list({m.id for m in shown}), country)

    comp_rows = await session.execute(
        select(
            Competition,
            func.count(Match.id).filter(Match.status.in_(LIVE_STATUSES)),
            func.count(Match.id).filter(Match.status == MatchStatus.SCHEDULED, Match.kickoff_time >= now,
                                        Match.kickoff_time < now + timedelta(days=7)),
        )
        .outerjoin(Match, Match.competition_id == Competition.id)
        .where(or_(Competition.is_major.is_(True), Competition.priority >= 55))
        .group_by(Competition.id)
        .order_by(Competition.priority.desc())
    )
    rows = comp_rows.all()
    # During international breaks the big leagues are idle: lead with what's actually on.
    rows.sort(key=lambda r: (not (r[1] or r[2]), -r[0].priority))
    competitions = [
        CompetitionWithCounts(**competition_out(c).model_dump(), live_count=lc, upcoming_count=uc)
        for c, lc, uc in rows[:8]
    ]
    teams = (await session.scalars(select(Team).order_by(Team.popularity.desc(), Team.name).limit(12))).all()
    return HomeOut(
        server_time=now,
        demo_mode=settings.demo_mode,
        featured=Featured(mode=mode, match=match_out(featured_match, summaries.get(featured_match.id))
                          if featured_match else None),
        live=[match_out(m, summaries.get(m.id)) for m in live],
        next_matches=[match_out(m, summaries.get(m.id)) for m in next_matches],
        competitions=competitions,
        popular_teams=[team_out(t) for t in teams],
    )


@router.get("/matches", response_model=MatchPage, dependencies=[rate_limit("matches")])
async def matches(
    status: StatusFilter = "all",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    competition: str | None = Query(None, max_length=80),
    team: str | None = Query(None, max_length=80),
    teams: str | None = Query(None, max_length=2500, description="Comma-separated team slugs"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10_000),
    session: AsyncSession = Depends(get_session),
    country: str | None = Depends(viewer_country),
) -> MatchPage:
    team_list = team_slugs(teams)
    if teams and not team_list:
        return MatchPage(items=[], total=0, limit=limit, offset=offset)
    items, total = await list_matches(
        session, status=None if status == "all" else status, date_from=date_from, date_to=date_to,
        competition=competition, team=team, teams=team_list, limit=limit, offset=offset,
    )
    return MatchPage(items=await matches_out(session, items, country), total=total, limit=limit, offset=offset)


@router.get("/matches/live", response_model=list[MatchOut], dependencies=[rate_limit("matches")])
async def live_matches(
    session: AsyncSession = Depends(get_session), country: str | None = Depends(viewer_country)
) -> list[MatchOut]:
    items, _ = await list_matches(session, status="live", limit=100)
    return await matches_out(session, items, country)


@router.get("/matches/upcoming", response_model=list[MatchOut], dependencies=[rate_limit("matches")])
async def upcoming_matches(
    days: int = Query(7, ge=1, le=14),
    competition: str | None = Query(None, max_length=80),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    country: str | None = Depends(viewer_country),
) -> list[MatchOut]:
    now = utcnow()
    items, _ = await list_matches(session, status="upcoming", date_to=now + timedelta(days=days),
                                  competition=competition, limit=limit)
    return await matches_out(session, items, country)


async def _get_match(session: AsyncSession, ref: str) -> Match:
    query = match_select()
    query = query.where(Match.id == int(ref)) if ref.isdigit() else query.where(Match.slug == ref)
    match = (await session.scalars(query)).unique().first()
    if match is None:
        raise HTTPException(404, "Match not found")
    return match


@router.get("/matches/{ref}", response_model=MatchOut, dependencies=[rate_limit("matches")])
async def match_detail(
    ref: str, session: AsyncSession = Depends(get_session), country: str | None = Depends(viewer_country)
) -> MatchOut:
    match = await _get_match(session, ref)
    summaries = await source_summaries(session, [match.id], country)
    return match_out(match, summaries.get(match.id))


@router.get("/matches/{ref}/sources", response_model=MatchSources, dependencies=[rate_limit("sources")])
async def match_sources(
    ref: str, session: AsyncSession = Depends(get_session), country: str | None = Depends(viewer_country)
) -> MatchSources:
    match = await _get_match(session, ref)
    links = (
        await session.scalars(
            select(StreamLink)
            .options(joinedload(StreamLink.source))
            .where(StreamLink.match_id == match.id, StreamLink.status != LinkStatus.EXPIRED)
        )
    ).all()
    links = [link for link in links if link.source.enabled]
    reliability = await source_reliability(session, list({link.source_id for link in links}))
    summary = SourceSummary()
    items = []
    for link in links:
        health = HEALTH_OF_STATUS.get(link.status, "checking")
        setattr(summary, health, getattr(summary, health) + 1)
        summary.total += 1
        available = availability(link.regions, country)
        items.append(
            SourceLinkOut(
                id=link.id,
                health=health,
                status=link.status,
                error_code=link.error_code,
                message=error_message(link.error_code),
                label=link.label,
                link_type=link.link_type,
                language=link.language,
                quality=link.quality if link.quality_verified else None,
                last_checked_at=link.last_checked_at,
                last_ok_at=link.last_ok_at,
                response_time_ms=link.response_time_ms,
                redirect_hops=link.redirect_hops,
                watch_url=f"/api/links/{link.id}/go" if health != "offline" else None,
                source=SourceInfo(
                    key=link.source.key,
                    name=link.source.name,
                    type=link.source.connector_type,
                    domain=link.source.domain,
                    reliability=reliability[link.source_id],
                ),
                regions=[r for r in (link.regions or "").split(",") if r] or None,
                access=link.access,
                coverage=link.coverage,
                notes=link.notes,
                confirmed=link.confirmed,
                available=available,
                one_click=one_click(link, available) and health != "offline",
            )
        )
    # What you can watch where you are comes first; then one-click free streams, then working
    # sources, free before paid, official before the rest, fastest first.
    region_rank = {True: 0, None: 1, False: 2}
    items.sort(key=lambda i: (
        region_rank[i.available],
        not i.one_click,
        HEALTH_ORDER[i.health],
        ACCESS_RANK.get(i.access or "", 4),
        not i.confirmed,
        i.source.type != "official",
        i.response_time_ms or 10**6,
    ))
    return MatchSources(country=country, match_id=match.id, checked_at=utcnow(), summary=summary, items=items)


@router.get("/links/{link_id}/go", include_in_schema=False, dependencies=[rate_limit("matches")])
async def go(link_id: int, session: AsyncSession = Depends(get_session)) -> RedirectResponse:
    link = await session.get(StreamLink, link_id)
    if link is None or link.status == LinkStatus.EXPIRED:
        raise HTTPException(404, "This source is no longer available")
    recent_ok = link.last_ok_at and utcnow() - link.last_ok_at < timedelta(minutes=15)
    target = link.resolved_url if recent_ok and link.resolved_url else link.original_url
    if not target.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid destination")
    session.add(LinkClick(link_id=link.id, match_id=link.match_id, link_status=link.status))
    await session.commit()
    return RedirectResponse(target, status_code=302, headers={"Referrer-Policy": "no-referrer"})


def _espn_available(settings: Settings) -> bool:
    return settings.espn_enabled and not settings.demo_mode


@router.get("/matches/{ref}/details", response_model=MatchDetailsOut, dependencies=[rate_limit("matches")])
async def match_details(
    ref: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    engine: Engine = Depends(get_engine),
) -> MatchDetailsOut:
    """Line-ups, key events, team stats and recent form, when the fixture feed has them."""
    match = await _get_match(session, ref)
    if not _espn_available(settings):
        return MatchDetailsOut(available=False)
    event_id = await session.scalar(select(MatchExternalRef.external_id).where(
        MatchExternalRef.match_id == match.id, MatchExternalRef.provider == "espn"))
    data = await engine.details.match(event_id, match.status, match.kickoff_time, utcnow()) if event_id else None
    return MatchDetailsOut(**data) if data else MatchDetailsOut(available=False)


def _calendar_event(match: Match, settings: Settings, alarm: int | None = None) -> CalendarEvent:
    home, away = match.home_team.name, match.away_team.name
    summary = f"{home} vs {away}"
    if match.status == MatchStatus.FINISHED and match.score_home is not None and match.score_away is not None:
        summary = f"{home} {match.score_home}-{match.score_away} {away}"
    elif match.status == MatchStatus.POSTPONED:
        summary = f"Postponed: {summary}"
    url = f"{settings.public_base_url.rstrip('/')}/match/{match.slug}"
    competition = match.competition.name if match.competition else "Football"
    return CalendarEvent(
        uid=f"match-{match.id}@unitedbyfootball",
        start=match.kickoff_time,
        summary=summary,
        description=f"{competition}\nLive score and where to watch: {url}",
        location=match.venue,
        url=url,
        cancelled=match.status == MatchStatus.CANCELLED,
        alarm_minutes=alarm if match.status == MatchStatus.SCHEDULED else None,
    )


def _ics(body: str, filename: str, download: bool) -> Response:
    headers = {"Cache-Control": "public, max-age=300"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(body, media_type="text/calendar; charset=utf-8", headers=headers)


@router.get("/matches/{ref}/calendar.ics", include_in_schema=False, dependencies=[rate_limit("matches")])
async def match_calendar(
    ref: str,
    alarm: int = Query(15, ge=0, le=1440, description="Reminder this many minutes before kick-off (0 for none)"),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    match = await _get_match(session, ref)
    event = _calendar_event(match, settings, alarm or None)
    return _ics(build_calendar([event], event.summary, utcnow()), f"{match.slug}.ics", download=True)


@router.get("/calendar/teams.ics", include_in_schema=False, dependencies=[rate_limit("matches")])
async def teams_calendar(
    teams: str = Query(..., max_length=2500, description="Comma-separated team slugs"),
    alarm: int = Query(0, ge=0, le=1440),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    """A subscribable feed of every known fixture for the given teams (recent results included)."""
    slugs = team_slugs(teams)
    if not slugs:
        raise HTTPException(400, "No valid team slugs")
    now = utcnow()
    items, _ = await list_matches(session, teams=slugs, date_from=now - timedelta(days=14), limit=300)
    names = (await session.scalars(select(Team.name).where(Team.slug.in_(slugs)).order_by(Team.name))).all()
    title = f"{names[0]} fixtures" if len(names) == 1 else "My teams"
    body = build_calendar([_calendar_event(m, settings, alarm or None) for m in items],
                          f"{title} · United By Football", now, refresh_hours=6)
    return _ics(body, "my-teams.ics", download=False)


@router.get("/competitions/{slug}/table", response_model=TableOut, dependencies=[rate_limit("matches")])
async def competition_table(
    slug: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    engine: Engine = Depends(get_engine),
) -> TableOut:
    comp = await session.scalar(select(Competition).where(Competition.slug == slug))
    if comp is None:
        raise HTTPException(404, "Competition not found")
    if not _espn_available(settings) or not comp.espn_league:
        return TableOut(available=False)
    data = await engine.details.standings(comp.espn_league)
    if not data or not data["available"]:
        return TableOut(available=False)
    ext_ids = {r["external_id"] for g in data["groups"] for r in g["rows"] if r["external_id"]}
    known = await session.execute(
        select(TeamExternalRef.external_id, Team).join(Team, Team.id == TeamExternalRef.team_id)
        .where(TeamExternalRef.provider == "espn", TeamExternalRef.external_id.in_(ext_ids)))
    teams = {ext: team_out(team) for ext, team in known.all()}
    groups = [
        TableGroup(name=g["name"], rows=[
            TableRow(**{k: v for k, v in r.items() if k != "external_id"}, team=teams.get(r["external_id"]))
            for r in g["rows"]])
        for g in data["groups"]
    ]
    return TableOut(available=True, season=data["season"], groups=groups, legend=data["legend"])


@router.get("/competitions", response_model=list[CompetitionWithCounts], dependencies=[rate_limit("matches")])
async def competitions(session: AsyncSession = Depends(get_session)) -> list[CompetitionWithCounts]:
    now = utcnow()
    rows = await session.execute(
        select(
            Competition,
            func.count(Match.id).filter(Match.status.in_(LIVE_STATUSES)),
            func.count(Match.id).filter(Match.status == MatchStatus.SCHEDULED, Match.kickoff_time >= now,
                                        Match.kickoff_time < now + timedelta(days=7)),
        )
        .outerjoin(Match, Match.competition_id == Competition.id)
        .group_by(Competition.id)
        .order_by(Competition.is_major.desc(), Competition.priority.desc(), Competition.name)
    )
    return [CompetitionWithCounts(**competition_out(c).model_dump(), live_count=lc, upcoming_count=uc)
            for c, lc, uc in rows.all()]


@router.get("/competitions/{slug}", response_model=CompetitionOut, dependencies=[rate_limit("matches")])
async def competition_detail(slug: str, session: AsyncSession = Depends(get_session)) -> CompetitionOut:
    comp = await session.scalar(select(Competition).where(Competition.slug == slug))
    if comp is None:
        raise HTTPException(404, "Competition not found")
    return competition_out(comp)


@router.get("/teams", response_model=list[TeamOut], dependencies=[rate_limit("matches")])
async def teams(
    competition: str | None = Query(None, max_length=80),
    session: AsyncSession = Depends(get_session),
) -> list[TeamOut]:
    query = select(Team).order_by(Team.popularity.desc(), Team.name)
    if competition:
        comp_id = select(Competition.id).where(Competition.slug == competition).scalar_subquery()
        in_comp = select(Match.home_team_id).where(Match.competition_id == comp_id).union(
            select(Match.away_team_id).where(Match.competition_id == comp_id))
        query = query.where(Team.id.in_(in_comp))
    return [team_out(t) for t in (await session.scalars(query.limit(200))).all()]


@router.get("/teams/{slug}", response_model=TeamDetailOut, dependencies=[rate_limit("matches")])
async def team_detail(
    slug: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    engine: Engine = Depends(get_engine),
) -> TeamDetailOut:
    team = await session.scalar(select(Team).where(Team.slug == slug))
    if team is None:
        raise HTTPException(404, "Team not found")
    media = await engine.media.get_or_enrich(team.id) if settings.media_enabled and not settings.demo_mode else None
    if media is not None:
        await session.refresh(team)  # enrichment may have filled in the country
    if media is None:
        media_out = TeamMediaOut(status="pending" if settings.media_enabled and not settings.demo_mode else "none")
    else:
        photo = PhotoOut(url=media.photo_url, page=media.photo_page, subject=media.photo_subject,
                         author=media.photo_author, license=media.photo_license,
                         license_url=media.photo_license_url) if media.photo_url else None
        media_out = TeamMediaOut(status=media.status, founded=media.founded, stadium=media.stadium,
                                 capacity=media.capacity, website=media.website, photo=photo)
    return TeamDetailOut(**team_out(team).model_dump(), media=media_out)


@router.get("/search", response_model=SearchOut, dependencies=[rate_limit("search")])
async def search(
    q: str = Query(..., min_length=1, max_length=60),
    session: AsyncSession = Depends(get_session),
    country: str | None = Depends(viewer_country),
) -> SearchOut:
    query = q.strip()
    normalized = normalize_name(query)
    if len(query) < 2 or not normalized:
        return SearchOut(query=query, teams=[], competitions=[], matches=[])

    alias_team_ids = select(TeamAlias.team_id).where(TeamAlias.alias.contains(normalized, autoescape=True))
    teams = (
        await session.scalars(
            select(Team)
            .where(or_(Team.name.icontains(query, autoescape=True), Team.id.in_(alias_team_ids)))
            .order_by(Team.popularity.desc(), Team.name)
            .limit(8)
        )
    ).all()
    comps = (
        await session.scalars(
            select(Competition)
            .where(or_(Competition.name.icontains(query, autoescape=True),
                       Competition.short_name.icontains(query, autoescape=True),
                       Competition.code.ilike(query)))
            .order_by(Competition.priority.desc())
            .limit(5)
        )
    ).all()

    team_ids = [t.id for t in teams]
    comp_ids = [c.id for c in comps]
    matches: list[Match] = []
    if team_ids or comp_ids:
        now = utcnow()
        conditions = []
        if team_ids:
            conditions += [Match.home_team_id.in_(team_ids), Match.away_team_id.in_(team_ids)]
        if comp_ids:
            conditions.append(Match.competition_id.in_(comp_ids))
        rows = await session.scalars(
            match_select()
            .where(or_(*conditions), Match.kickoff_time >= now - timedelta(days=3),
                   Match.kickoff_time <= now + timedelta(days=10))
            .order_by(Match.kickoff_time)
            .limit(120)
        )
        candidates = list(rows.unique().all())
        rank = {MatchStatus.LIVE: 0, MatchStatus.HALFTIME: 0, MatchStatus.SCHEDULED: 1}

        def order(m: Match):
            r = rank.get(m.status, 2)
            # live first, then soonest upcoming, then most recent results
            return (r, m.kickoff_time.timestamp() * (-1 if r == 2 else 1))

        matches = sorted(candidates, key=order)[:20]

    return SearchOut(
        query=query,
        teams=[team_out(t) for t in teams],
        competitions=[competition_out(c) for c in comps],
        matches=await matches_out(session, matches, country),
    )
