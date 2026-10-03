"""Read-side queries shared by the public and admin APIs."""

import time
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.schemas import (
    CompetitionOut,
    MatchOut,
    Reliability,
    Score,
    SourceSummary,
    TeamOut,
    TopSource,
)
from app.database.models import (
    LIVE_STATUSES,
    Competition,
    HealthCheck,
    LinkStatus,
    Match,
    MatchStatus,
    Source,
    StreamLink,
    Team,
)
from app.utils.time import utcnow

HEALTH_OF_STATUS = {
    LinkStatus.VALID: "working",
    LinkStatus.DISCOVERED: "checking",
    LinkStatus.RESOLVING: "checking",
    LinkStatus.RESOLVED: "unverified",
    LinkStatus.INVALID: "offline",
    LinkStatus.ERROR: "offline",
}

ERROR_MESSAGES = {
    "HTTP_401": "The site restricts automated checks",
    "HTTP_403": "The site restricts automated checks",
    "HTTP_404": "Page not found",
    "HTTP_410": "Removed by the source",
    "HTTP_429": "The source is rate-limiting checks",
    "TIMEOUT": "Didn't respond in time",
    "DNS_ERROR": "Domain not found",
    "CONNECTION_ERROR": "Couldn't connect",
    "TOO_MANY_REDIRECTS": "Too many redirects",
    "BLOCKED_BY_POLICY": "Blocked by safety policy",
    "INVALID_URL": "Invalid link",
    "NO_LONGER_AVAILABLE": "No longer available",
    "DESTINATION_CHANGED": "Destination changed recently",
    "CHECK_FAILED": "Check failed",
    "GEO_RESTRICTED": "Region-restricted — couldn't verify from our checker's location",
    "UNREACHABLE_FROM_CHECKER": "Couldn't verify from our location — it may only open in its own country",
}


ACCESS_RANK = {"free": 0, "free_account": 1, "licence": 2, "subscription": 3}


def availability(regions: str | None, country: str | None) -> bool | None:
    """Can a viewer in `country` watch a source limited to `regions`? None when unknown."""
    if not regions or not country:
        return None
    codes = [r.strip().upper() for r in regions.split(",") if r.strip()]
    if f"!{country}" in codes:
        return False
    return "*" in codes or country in codes


def one_click(link: StreamLink, available: bool | None) -> bool:
    """Good enough to send someone straight to: free, watchable here, and actually showing it."""
    return (
        link.access in ("free", "free_account")
        and available is not False
        and (link.coverage == "all" or bool(link.confirmed))
    )


def error_message(code: str | None) -> str | None:
    if not code:
        return None
    if code in ERROR_MESSAGES:
        return ERROR_MESSAGES[code]
    if code.startswith("HTTP_5"):
        return "The source is having problems"
    return code.replace("_", " ").capitalize()


def match_select() -> Select:
    return select(Match).options(
        joinedload(Match.home_team), joinedload(Match.away_team), joinedload(Match.competition)
    )


def team_out(team: Team) -> TeamOut:
    return TeamOut.model_validate(team, from_attributes=True)


def competition_out(comp: Competition | None) -> CompetitionOut | None:
    return CompetitionOut.model_validate(comp, from_attributes=True) if comp else None


def importance(match: Match) -> float:
    priority = match.competition.priority if match.competition else 10
    return priority + (match.home_team.popularity + match.away_team.popularity) / 2


def match_out(match: Match, summary: SourceSummary | None = None) -> MatchOut:
    has_score = match.status not in (MatchStatus.SCHEDULED, MatchStatus.POSTPONED, MatchStatus.CANCELLED)
    return MatchOut(
        id=match.id,
        slug=match.slug,
        status=match.status,
        is_live=match.status in LIVE_STATUSES,
        minute=match.minute,
        minute_display=match.minute_display,
        kickoff_time=match.kickoff_time,
        home=team_out(match.home_team),
        away=team_out(match.away_team),
        score=Score(home=match.score_home, away=match.score_away) if has_score and match.score_home is not None else None,
        competition=competition_out(match.competition),
        venue=match.venue,
        referee=match.referee,
        sources=summary or SourceSummary(),
    )


async def source_summaries(session: AsyncSession, match_ids: list[int], country: str | None = None) -> dict[int, SourceSummary]:
    if not match_ids:
        return {}
    rows = await session.execute(
        select(StreamLink.match_id, StreamLink.status, func.count(StreamLink.id))
        .where(StreamLink.match_id.in_(match_ids), StreamLink.status != LinkStatus.EXPIRED)
        .group_by(StreamLink.match_id, StreamLink.status)
    )
    out: dict[int, SourceSummary] = defaultdict(SourceSummary)
    for match_id, status, count in rows.all():
        summary = out[match_id]
        health = HEALTH_OF_STATUS.get(status)
        if health:
            setattr(summary, health, getattr(summary, health) + count)
            summary.total += count

    # The source a card names: watchable here first, then free and showing this match, then
    # official, then fastest. Reachable-but-unverifiable sources count (geo-blocked players).
    rows = await session.scalars(
        select(StreamLink)
        .options(joinedload(StreamLink.source))
        .join(Source, Source.id == StreamLink.source_id)
        .where(StreamLink.match_id.in_(match_ids), Source.enabled.is_(True),
               StreamLink.status.in_((LinkStatus.VALID, LinkStatus.RESOLVED)))
    )
    best: dict[int, tuple] = {}
    for link in rows.unique().all():
        available = availability(link.regions, country)
        if available is False:
            continue
        direct = one_click(link, available)
        rank = (
            not direct,
            available is not True,
            ACCESS_RANK.get(link.access or "", 4),
            link.status != LinkStatus.VALID,
            link.source.connector_type != "official",
            link.response_time_ms if link.response_time_ms is not None else 10**6,
        )
        if link.match_id not in best or rank < best[link.match_id][0]:
            best[link.match_id] = (rank, link, available, direct)
    for match_id, (_, link, available, direct) in best.items():
        out[match_id].top = TopSource(
            label=link.label or link.source.name,
            type=link.source.connector_type,
            access=link.access,
            available=available,
            one_click=direct,
            watch_url=f"/api/links/{link.id}/go",
        )
    return dict(out)


async def matches_out(session: AsyncSession, matches: list[Match], country: str | None = None) -> list[MatchOut]:
    summaries = await source_summaries(session, [m.id for m in matches], country)
    return [match_out(m, summaries.get(m.id)) for m in matches]


def apply_status_filter(query: Select, status: str | None, now: datetime) -> Select:
    if status == "live":
        return query.where(Match.status.in_(LIVE_STATUSES))
    if status == "upcoming":
        return query.where(Match.status == MatchStatus.SCHEDULED, Match.kickoff_time >= now - timedelta(hours=2))
    if status == "finished":
        return query.where(Match.status == MatchStatus.FINISHED)
    return query


# Pseudo competition slug for every national-team competition.
INTERNATIONALS = "internationals"


async def list_matches(
    session: AsyncSession,
    *,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    competition: str | None = None,
    team: str | None = None,
    teams: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
    with_total: bool = True,
) -> tuple[list[Match], int]:
    """Matches for a filter, and how many there are in all.

    `with_total=False` skips the count, which is a second database round trip over the same
    joined query. Callers that only list results should pass it: against a hosted database
    that round trip costs as much as the query it accompanies.
    """
    now = utcnow()
    filters = match_select()
    filters = apply_status_filter(filters, status, now)
    if date_from:
        filters = filters.where(Match.kickoff_time >= date_from)
    if date_to:
        filters = filters.where(Match.kickoff_time < date_to)
    if competition:
        comp_ids = select(Competition.id)
        if competition == "other":
            comp_ids = comp_ids.where(Competition.is_major.is_(False), Competition.national_teams.isnot(True))
        elif competition == INTERNATIONALS:
            comp_ids = comp_ids.where(Competition.national_teams.is_(True))
        else:
            comp_ids = comp_ids.where(Competition.slug == competition)
        filters = filters.where(Match.competition_id.in_(comp_ids))
    if team:
        team_id = select(Team.id).where(Team.slug == team).scalar_subquery()
        filters = filters.where(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))
    if teams:
        team_ids = select(Team.id).where(Team.slug.in_(teams))
        filters = filters.where(or_(Match.home_team_id.in_(team_ids), Match.away_team_id.in_(team_ids)))

    total = (
        await session.scalar(select(func.count()).select_from(filters.order_by(None).subquery()))
        if with_total
        else 0
    )
    order = Match.kickoff_time.desc() if status == "finished" else Match.kickoff_time.asc()
    rows = await session.scalars(filters.order_by(order, Match.id).limit(limit).offset(offset))
    matches = list(rows.unique().all())
    if status == "live":
        matches.sort(key=importance, reverse=True)
    return matches, total or 0


_reliability_cache: dict[int, tuple[float, Reliability]] = {}


def reliability_label(ok: int, total: int) -> Reliability:
    if total < 5:
        return Reliability(label="New source", uptime_pct=None, checks=total)
    pct = round(100 * ok / total, 1)
    if pct >= 90:
        label = "Usually available"
    elif pct >= 60:
        label = "Sometimes available"
    else:
        label = "Often unavailable"
    return Reliability(label=label, uptime_pct=pct, checks=total)


async def source_reliability(session: AsyncSession, source_ids: list[int]) -> dict[int, Reliability]:
    """Historical availability per source over the last 24h, summarized into a plain label."""
    now = time.monotonic()
    result = {sid: hit[1] for sid in source_ids if (hit := _reliability_cache.get(sid)) and now - hit[0] < 60}
    missing = [sid for sid in source_ids if sid not in result]
    if missing:
        since = utcnow() - timedelta(hours=24)
        rows = await session.execute(
            select(
                StreamLink.source_id,
                func.count(HealthCheck.id),
                func.sum(case((HealthCheck.status == LinkStatus.VALID, 1), else_=0)),
            )
            .join(StreamLink, StreamLink.id == HealthCheck.link_id)
            .where(StreamLink.source_id.in_(missing), HealthCheck.checked_at >= since,
                   HealthCheck.status != LinkStatus.RESOLVED)
            .group_by(StreamLink.source_id)
        )
        counts = {sid: (int(ok or 0), int(total or 0)) for sid, total, ok in rows.all()}
        for sid in missing:
            ok, total = counts.get(sid, (0, 0))
            rel = reliability_label(ok, total)
            _reliability_cache[sid] = (now, rel)
            result[sid] = rel
    return result
