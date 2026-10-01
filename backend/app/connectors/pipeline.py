"""Source ingestion pipeline: connector -> normalize -> associate with match -> store.

Each connector runs in isolation: a timeout, HTTP error or parser crash is recorded
against that source only.
"""

import asyncio
import hashlib
import json
import logging
from datetime import timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.config import Settings
from app.connectors.base import ConnectorContext, DiscoveredMatch, KnownMatch, SourceConnector
from app.database.models import Competition, CrawlRun, LinkStatus, Match, Source, StreamLink, Team
from app.database.runs import finish_run, start_run
from app.database.session import Database
from app.match.matcher import MatchIndex
from app.match.teams import TeamDirectory
from app.resolver.ssrf import InvalidURLError, URLGuard, URLPolicyError, parse_http_url
from app.utils.text import sanitize_text
from app.utils.time import ensure_utc, utcnow

log = logging.getLogger(__name__)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def classify_error(exc: BaseException) -> str:
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return "TIMEOUT"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP_{exc.response.status_code}"
    if isinstance(exc, URLPolicyError):
        return exc.code
    if isinstance(exc, httpx.ConnectError):
        return "CONNECTION_ERROR"
    if isinstance(exc, httpx.HTTPError):
        return "HTTP_ERROR"
    return "PARSER_ERROR"


async def load_known_matches(session, now) -> list[KnownMatch]:
    home, away = aliased(Team), aliased(Team)
    rows = await session.execute(
        select(Match.id, home.name, away.name, Match.kickoff_time, Competition.code, Match.status,
               Competition.slug, home.short_name, away.short_name)
        .join(home, home.id == Match.home_team_id)
        .join(away, away.id == Match.away_team_id)
        .outerjoin(Competition, Competition.id == Match.competition_id)
        .where(Match.kickoff_time >= now - timedelta(hours=3), Match.kickoff_time <= now + timedelta(days=8))
        .order_by(Match.kickoff_time)
    )
    return [KnownMatch(*row) for row in rows.all()]


async def run_connector(
    db: Database,
    connector: SourceConnector,
    http: httpx.AsyncClient,
    guard: URLGuard,
    settings: Settings,
) -> dict:
    now = utcnow()
    async with db.sessions() as session:
        source = await session.scalar(select(Source).where(Source.key == connector.key))
        if source is None or not source.enabled:
            return {"source": connector.key, "status": "disabled"}
        source_id = source.id
        run = await start_run(session, "discovery", connector.key)
        run_id = run.id
        await session.commit()
        known = await load_known_matches(session, now)

    ctx = ConnectorContext(settings=settings, http=http, guard=guard, now=now, matches=known,
                           log=logging.getLogger(f"connector.{connector.key}"))
    try:
        listings = await asyncio.wait_for(connector.discover(ctx), timeout=connector.timeout)
    except Exception as exc:
        code = classify_error(exc)
        log.warning("connector %s failed (%s): %s", connector.key, code, exc)
        async with db.sessions() as session:
            run = await session.get(CrawlRun, run_id)
            source = await session.get(Source, source_id)
            finish_run(run, "error", f"{type(exc).__name__}: {exc}", code)
            source.last_run_at, source.last_status = utcnow(), "error"
            source.last_error = f"{code}: {exc}"[:500]
            source.consecutive_failures += 1
            await session.commit()
        return {"source": connector.key, "status": "error", "error_code": code}

    async with db.sessions() as session:
        run = await session.get(CrawlRun, run_id)
        source = await session.get(Source, source_id)
        stats = await _store_listings(session, source, listings, now)
        run.items_found = len(listings)
        run.matched, run.unmatched = stats["matched"], stats["unmatched"]
        run.links_new, run.links_updated, run.links_expired = stats["new"], stats["updated"], stats["expired"]
        run.details = json.dumps({"unmatched": stats["unmatched_samples"], "invalid_urls": stats["invalid"]})
        if stats["empty_guard"]:
            finish_run(run, "error", "Connector returned no listings; kept existing links", "EMPTY_RESULT")
            source.last_status = "error"
            source.last_error = "EMPTY_RESULT"
            source.consecutive_failures += 1
        else:
            finish_run(run)
            source.last_status, source.last_error = "ok", None
            source.last_success_at = utcnow()
            source.consecutive_failures = 0
        source.last_run_at = utcnow()
        await session.commit()
    return {"source": connector.key, "status": run.status, **{k: v for k, v in stats.items() if k != "empty_guard"}}


async def _store_listings(session, source: Source, listings: list[DiscoveredMatch], now) -> dict:
    directory = await TeamDirectory.load(session)
    index = await MatchIndex.load(session, directory, now)
    existing_rows = await session.scalars(
        select(StreamLink)
        .join(Match, Match.id == StreamLink.match_id)
        .where(StreamLink.source_id == source.id, Match.kickoff_time >= now - timedelta(days=2))
    )
    existing = {(link.match_id, link.url_hash): link for link in existing_rows.all()}
    stats = {"matched": 0, "unmatched": 0, "new": 0, "updated": 0, "expired": 0, "invalid": 0,
             "unmatched_samples": [], "empty_guard": False}
    seen: set[tuple[int, str]] = set()

    for listing in listings:
        match_id = listing.match_id
        if match_id is None:
            kickoff = ensure_utc(listing.kickoff) if listing.kickoff else None
            found = index.find(listing.home, listing.away, now, kickoff, listing.competition)
            match_id = found.match_id if found else None
        if match_id is None:
            stats["unmatched"] += 1
            if len(stats["unmatched_samples"]) < 10:
                stats["unmatched_samples"].append(f"{listing.home} v {listing.away}"[:120])
            continue
        stats["matched"] += 1
        for discovered in listing.links:
            try:
                parse_http_url(discovered.url)
            except InvalidURLError:
                stats["invalid"] += 1
                continue
            key = (match_id, url_hash(discovered.url))
            if key in seen:
                continue
            seen.add(key)
            link = existing.get(key)
            if link is None:
                link = StreamLink(match_id=match_id, source_id=source.id, original_url=discovered.url,
                                  url_hash=key[1], status=LinkStatus.DISCOVERED)
                session.add(link)
                existing[key] = link
                stats["new"] += 1
            else:
                if link.status == LinkStatus.EXPIRED:
                    link.status, link.error_code = LinkStatus.DISCOVERED, None
                stats["updated"] += 1
            link.label = sanitize_text(discovered.label, 120)
            link.link_type = sanitize_text(discovered.link_type, 20) or "watch"
            link.language = sanitize_text(discovered.language, 40)
            link.quality = sanitize_text(discovered.quality, 20)
            link.regions = ",".join(r.strip().upper() for r in discovered.regions)[:400] if discovered.regions else None
            link.access = discovered.access
            link.coverage = discovered.coverage
            link.notes = sanitize_text(discovered.notes, 200)
            link.confirmed = discovered.confirmed
            link.last_seen_at = now

    active = [link for k, link in existing.items() if k not in seen and link.status != LinkStatus.EXPIRED]
    if not listings and active:
        # A source that suddenly lists nothing has most likely changed its layout.
        # Keep what we have instead of wiping every link.
        stats["empty_guard"] = True
        return stats
    for link in active:
        link.status, link.error_code = LinkStatus.EXPIRED, "NO_LONGER_AVAILABLE"
        stats["expired"] += 1
    return stats
