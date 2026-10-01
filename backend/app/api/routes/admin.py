import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_engine, get_session, require_admin
from app.api.queries import HEALTH_OF_STATUS, error_message, list_matches, matches_out
from app.database.models import (
    LIVE_STATUSES,
    CrawlRun,
    HealthCheck,
    LinkClick,
    LinkStatus,
    Match,
    MatchStatus,
    Source,
    StreamLink,
)
from app.scheduler.engine import Engine
from app.utils.time import utcnow

router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)], tags=["admin"])


class SourcePatch(BaseModel):
    enabled: bool


class ValidateRequest(BaseModel):
    link_ids: list[int] | None = Field(default=None, max_length=500)
    force: bool = False


def _source_light(source: Source) -> str:
    if not source.enabled:
        return "disabled"
    if source.last_status is None:
        return "pending"
    if source.consecutive_failures >= 2:
        return "down"
    if source.last_status != "ok":
        return "degraded"
    return "ok"


@router.get("/admin/check")
async def check() -> dict:
    return {"ok": True}


@router.get("/admin/overview")
async def overview(session: AsyncSession = Depends(get_session)) -> dict:
    now = utcnow()
    day_ago = now - timedelta(hours=24)
    live = await session.scalar(select(func.count(Match.id)).where(Match.status.in_(LIVE_STATUSES)))
    upcoming = await session.scalar(
        select(func.count(Match.id)).where(Match.status == MatchStatus.SCHEDULED, Match.kickoff_time >= now,
                                           Match.kickoff_time < now + timedelta(days=7))
    )
    finished = await session.scalar(
        select(func.count(Match.id)).where(Match.status == MatchStatus.FINISHED, Match.kickoff_time >= day_ago)
    )
    link_rows = (await session.execute(select(StreamLink.status, func.count(StreamLink.id)).group_by(StreamLink.status))).all()
    links = {"discovered": 0, "working": 0, "checking": 0, "unverified": 0, "offline": 0, "expired": 0}
    for status, count in link_rows:
        if status == LinkStatus.EXPIRED:
            links["expired"] += count
        else:
            links[HEALTH_OF_STATUS.get(status, "checking")] += count
            links["discovered"] += count

    checks_total, checks_ok, avg_ms = (await session.execute(
        select(
            func.count(HealthCheck.id),
            func.sum(case((HealthCheck.status == LinkStatus.VALID, 1), else_=0)),
            func.avg(case((HealthCheck.status == LinkStatus.VALID, HealthCheck.response_time_ms), else_=None)),
        ).where(HealthCheck.checked_at >= day_ago)
    )).one()
    clicks_total, clicks_ok = (await session.execute(
        select(func.count(LinkClick.id), func.sum(case((LinkClick.link_status == LinkStatus.VALID, 1), else_=0)))
        .where(LinkClick.clicked_at >= day_ago)
    )).one()
    last = {}
    for job in ("fixtures", "discovery", "health"):
        last[job] = await session.scalar(select(func.max(CrawlRun.finished_at)).where(CrawlRun.job == job))
    return {
        "server_time": now,
        "matches": {"live": live or 0, "upcoming_7d": upcoming or 0, "finished_24h": finished or 0},
        "links": links,
        "health_24h": {
            "checks": checks_total or 0,
            "success_rate": round(100 * (checks_ok or 0) / checks_total, 1) if checks_total else None,
            "avg_latency_ms": round(avg_ms) if avg_ms else None,
        },
        "clicks_24h": {
            "total": clicks_total or 0,
            "to_working_pct": round(100 * (clicks_ok or 0) / clicks_total, 1) if clicks_total else None,
        },
        "last_run": last,
    }


@router.get("/admin/sources")
async def sources(session: AsyncSession = Depends(get_session)) -> list[dict]:
    day_ago = utcnow() - timedelta(hours=24)
    link_counts = {
        sid: (total, working)
        for sid, total, working in (await session.execute(
            select(StreamLink.source_id, func.count(StreamLink.id),
                   func.sum(case((StreamLink.status == LinkStatus.VALID, 1), else_=0)))
            .where(StreamLink.status != LinkStatus.EXPIRED)
            .group_by(StreamLink.source_id)
        )).all()
    }
    uptime = {
        sid: (total, ok)
        for sid, total, ok in (await session.execute(
            select(StreamLink.source_id, func.count(HealthCheck.id),
                   func.sum(case((HealthCheck.status == LinkStatus.VALID, 1), else_=0)))
            .join(StreamLink, StreamLink.id == HealthCheck.link_id)
            .where(HealthCheck.checked_at >= day_ago, HealthCheck.status != LinkStatus.RESOLVED)
            .group_by(StreamLink.source_id)
        )).all()
    }
    out = []
    for s in (await session.scalars(select(Source).order_by(Source.name))).all():
        total, working = link_counts.get(s.id, (0, 0))
        checks, ok = uptime.get(s.id, (0, 0))
        out.append({
            "key": s.key, "name": s.name, "type": s.connector_type, "domain": s.domain, "enabled": s.enabled,
            "description": s.description, "light": _source_light(s), "last_run_at": s.last_run_at,
            "last_success_at": s.last_success_at, "last_status": s.last_status, "last_error": s.last_error,
            "consecutive_failures": s.consecutive_failures, "links_active": total, "links_working": int(working or 0),
            "uptime_24h": round(100 * (ok or 0) / checks, 1) if checks else None,
        })
    return out


@router.patch("/admin/sources/{key}")
async def patch_source(key: str, body: SourcePatch, session: AsyncSession = Depends(get_session)) -> dict:
    source = await session.scalar(select(Source).where(Source.key == key))
    if source is None:
        raise HTTPException(404, "Unknown source")
    source.enabled = body.enabled
    await session.commit()
    return {"key": key, "enabled": source.enabled}


@router.get("/admin/runs")
async def runs(
    job: str | None = Query(None, pattern="^(fixtures|discovery|health)$"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    query = select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(limit)
    if job:
        query = query.where(CrawlRun.job == job)
    out = []
    for r in (await session.scalars(query)).all():
        out.append({
            "id": r.id, "job": r.job, "connector_key": r.connector_key, "status": r.status,
            "started_at": r.started_at, "finished_at": r.finished_at,
            "duration_ms": int((r.finished_at - r.started_at).total_seconds() * 1000) if r.finished_at else None,
            "items_found": r.items_found, "matched": r.matched, "unmatched": r.unmatched,
            "links_new": r.links_new, "links_updated": r.links_updated, "links_expired": r.links_expired,
            "error_code": r.error_code, "error": r.error,
            "details": json.loads(r.details) if r.details else None,
        })
    return out


@router.get("/admin/links")
async def links(
    health: str | None = Query(None, pattern="^(working|checking|unverified|offline|expired)$"),
    source: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    query = (
        select(StreamLink)
        .options(joinedload(StreamLink.source), joinedload(StreamLink.match).joinedload(Match.home_team),
                 joinedload(StreamLink.match).joinedload(Match.away_team))
        .order_by(StreamLink.last_checked_at.desc().nulls_first(), StreamLink.id.desc())
        .limit(limit)
    )
    if health == "expired":
        query = query.where(StreamLink.status == LinkStatus.EXPIRED)
    elif health:
        query = query.where(StreamLink.status.in_([s for s, h in HEALTH_OF_STATUS.items() if h == health]))
    else:
        query = query.where(StreamLink.status != LinkStatus.EXPIRED)
    if source:
        query = query.where(StreamLink.source.has(Source.key == source))
    out = []
    for link in (await session.scalars(query)).unique().all():
        out.append({
            "id": link.id, "match": f"{link.match.home_team.name} vs {link.match.away_team.name}",
            "match_slug": link.match.slug, "source": link.source.name, "label": link.label,
            "status": link.status, "health": HEALTH_OF_STATUS.get(link.status, "expired"),
            "error_code": link.error_code, "message": error_message(link.error_code),
            "http_status": link.http_status, "original_url": link.original_url, "resolved_url": link.resolved_url,
            "redirect_hops": link.redirect_hops, "response_time_ms": link.response_time_ms,
            "last_checked_at": link.last_checked_at, "check_count": link.check_count, "fail_count": link.fail_count,
        })
    return out


@router.get("/admin/matches")
async def admin_matches(
    status: str | None = Query(None, pattern="^(live|upcoming|finished)$"),
    limit: int = Query(100, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    items, total = await list_matches(session, status=status, date_from=utcnow() - timedelta(hours=30), limit=limit)
    return {"total": total, "items": await matches_out(session, items)}


@router.post("/sources/run")
async def run_sources(source: str | None = None, engine: Engine = Depends(get_engine)) -> dict:
    keys = [source] if source else None
    if source and source not in {c.key for c in engine.connectors}:
        raise HTTPException(404, "Unknown or inactive source")
    return {"results": await engine.run_sources(keys)}


@router.post("/links/validate")
async def validate_links(body: ValidateRequest | None = None, engine: Engine = Depends(get_engine)) -> dict:
    body = body or ValidateRequest()
    return await engine.validate_links(link_ids=body.link_ids, force=body.force)


@router.post("/matches/sync")
async def sync_matches(engine: Engine = Depends(get_engine)) -> dict:
    return {"results": await engine.sync_fixtures()}
