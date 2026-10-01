"""Health-check cycle: pick links that are due, check each unique URL once, persist.

Cadence follows the match: links for live matches are re-checked every
`health_live_interval` seconds, links for matches starting soon less often,
everything else rarely. Sources can set a politeness floor, and repeated
failures back off exponentially.
"""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import delete, select

from app.config import Settings
from app.database.models import (
    LIVE_STATUSES,
    HealthCheck,
    LinkStatus,
    Match,
    MatchStatus,
    Source,
    StreamLink,
)
from app.database.session import Database
from app.utils.time import utcnow
from app.validator.validator import CheckResult, LinkValidator

log = logging.getLogger(__name__)
ENDED = (MatchStatus.FINISHED, MatchStatus.CANCELLED, MatchStatus.POSTPONED)
EXPIRE_AFTER_KICKOFF = timedelta(hours=4)


@dataclass(frozen=True)
class CheckPolicy:
    offline_markers: tuple[str, ...] = ()
    geo_block_url_markers: tuple[str, ...] = ()
    unverifiable_errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class DueLink:
    id: int
    url: str
    policy: CheckPolicy


def check_interval(settings: Settings, match_status: str, kickoff: datetime, now: datetime,
                   min_interval: int | None, failures: int) -> int:
    if match_status in LIVE_STATUSES:
        base = settings.health_live_interval
    elif now - timedelta(hours=3) <= kickoff <= now + timedelta(hours=2):
        base = settings.health_soon_interval
    else:
        base = settings.health_default_interval
    base = max(base, min_interval or 0)
    if failures:
        base = base * (2 ** min(failures, 3))
    return base


def _host(url: str | None) -> str | None:
    return urlsplit(url).hostname if url else None


class HealthChecker:
    def __init__(self, db: Database, validator: LinkValidator, settings: Settings,
                 policies: dict[str, CheckPolicy]):
        self.db = db
        self.validator = validator
        self.settings = settings
        self.policies = policies

    async def run_cycle(self, link_ids: list[int] | None = None, force: bool = False) -> dict:
        now = utcnow()
        due: list[DueLink] = []
        expired = 0
        async with self.db.sessions() as session:
            query = (
                select(StreamLink, Match.status, Match.kickoff_time, Source.key, Source.enabled,
                       Source.min_check_interval)
                .join(Match, Match.id == StreamLink.match_id)
                .join(Source, Source.id == StreamLink.source_id)
                .where(StreamLink.status != LinkStatus.EXPIRED)
            )
            if link_ids:
                query = query.where(StreamLink.id.in_(link_ids))
            for link, m_status, kickoff, s_key, s_enabled, s_min in (await session.execute(query)).all():
                if m_status in ENDED and now - kickoff > EXPIRE_AFTER_KICKOFF:
                    link.status, link.error_code = LinkStatus.EXPIRED, "MATCH_ENDED"
                    expired += 1
                    continue
                if not s_enabled and not link_ids:
                    continue
                interval = check_interval(self.settings, m_status, kickoff, now, s_min, link.consecutive_failures)
                is_due = link.last_checked_at is None or (now - link.last_checked_at).total_seconds() >= interval
                if force or link_ids or is_due:
                    if link.status == LinkStatus.DISCOVERED:
                        link.status = LinkStatus.RESOLVING
                    due.append(DueLink(link.id, link.original_url, self.policies.get(s_key, CheckPolicy())))
            await session.commit()

        if not due:
            return {"checked": 0, "unique_urls": 0, "expired": expired}

        results = await self._check_unique(due)

        counts: dict[str, int] = defaultdict(int)
        async with self.db.sessions() as session:
            links = await session.scalars(select(StreamLink).where(StreamLink.id.in_([d.id for d in due])))
            by_id = {link.id: link for link in links.all()}
            checked_at = utcnow()
            for item in due:
                link = by_id.get(item.id)
                result = results.get(item.url)
                if link is None or result is None:
                    continue
                self._apply(link, result, checked_at)
                counts[result.status] += 1
                session.add(HealthCheck(link_id=link.id, checked_at=checked_at, status=result.status,
                                        http_status=result.http_status, response_time_ms=result.response_time_ms,
                                        error=link.error_code, resolved_url=result.final_url))
            await session.commit()
        return {"checked": len(due), "unique_urls": len(results), "expired": expired, "by_status": dict(counts)}

    async def _check_unique(self, due: list[DueLink]) -> dict[str, CheckResult]:
        # The same URL can be listed by several sources; check it once, applying every policy.
        policies: dict[str, CheckPolicy] = {}
        for item in due:
            prev = policies.get(item.url, CheckPolicy())
            policies[item.url] = CheckPolicy(
                tuple({*prev.offline_markers, *item.policy.offline_markers}),
                tuple({*prev.geo_block_url_markers, *item.policy.geo_block_url_markers}),
                tuple({*prev.unverifiable_errors, *item.policy.unverifiable_errors}),
            )
        global_sem = asyncio.Semaphore(self.settings.health_concurrency)
        host_sems: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self.settings.health_per_host_concurrency)
        )

        async def one(url: str) -> tuple[str, CheckResult]:
            async with global_sem, host_sems[_host(url) or ""]:
                try:
                    policy = policies[url]
                    result = await self.validator.check(url, policy.offline_markers, policy.geo_block_url_markers)
                    if result.status == LinkStatus.ERROR and result.error_code in policy.unverifiable_errors:
                        result = CheckResult(LinkStatus.RESOLVED, "UNREACHABLE_FROM_CHECKER",
                                             response_time_ms=result.response_time_ms)
                    return url, result
                except Exception:  # never let one URL break the cycle
                    log.exception("unexpected error checking %s", url)
                    return url, CheckResult(LinkStatus.ERROR, "CHECK_FAILED")

        return dict(await asyncio.gather(*(one(url) for url in policies)))

    @staticmethod
    def _apply(link: StreamLink, result: CheckResult, now: datetime) -> None:
        previous_host = _host(link.resolved_url)
        link.check_count += 1
        link.last_checked_at = now
        link.http_status = result.http_status
        link.response_time_ms = result.response_time_ms
        link.redirect_hops = result.hops
        if result.final_url:
            link.resolved_url = result.final_url
        if result.verified_quality:
            link.quality, link.quality_verified = result.verified_quality, True
        if link.status == LinkStatus.EXPIRED:
            return  # expired by discovery while we were checking
        link.status = result.status
        new_host = _host(result.final_url)
        changed = bool(previous_host and new_host and previous_host != new_host)
        link.error_code = result.error_code or ("DESTINATION_CHANGED" if changed else None)
        if result.ok:
            link.last_ok_at = now
            link.consecutive_failures = 0
        elif result.status in (LinkStatus.INVALID, LinkStatus.ERROR):
            link.fail_count += 1
            link.consecutive_failures += 1


async def prune_health_checks(db: Database, keep_days: int = 7) -> int:
    async with db.sessions() as session:
        result = await session.execute(delete(HealthCheck).where(HealthCheck.checked_at < utcnow() - timedelta(days=keep_days)))
        await session.commit()
        return result.rowcount or 0
