"""The engine wires the match engine and the source engine together and runs them
on adaptive schedules:

* fixtures  — every few seconds while matches are live, every 10 min otherwise
* discovery — every 2 min near kickoff/live, 5 min when warm, 15 min when cold
* health    — ticks every 10 s; each link has its own due time (see validator.health)

All jobs can also be triggered from the admin API. Each job has its own lock so a
manual trigger never overlaps a scheduled run.
"""

import asyncio
import contextlib
import json
import logging
from datetime import timedelta

import httpx
from sqlalchemy import delete, func, select

from app.config import Settings
from app.connectors.base import SourceConnector
from app.connectors.pipeline import run_connector
from app.connectors.registry import build_connectors, sync_sources
from app.database.models import LIVE_STATUSES, CrawlRun, Match, MatchExternalRef, MatchStatus, Source
from app.database.runs import finish_run, start_run
from app.database.seed import seed_reference_data
from app.database.session import Database
from app.match.providers import build_providers
from app.match.providers.base import FixtureProvider
from app.match.sync import sync_provider
from app.media.service import MediaService
from app.resolver.resolver import LinkResolver
from app.resolver.ssrf import URLGuard
from app.utils.time import utcnow
from app.validator.health import CheckPolicy, HealthChecker, prune_health_checks
from app.validator.validator import LinkValidator

log = logging.getLogger(__name__)


DEMO_PROVIDER = "demo-fixtures"
DEMO_SOURCES = ("demo-stream-guide", "demo-event-feed")


async def purge_demo_data(db: Database) -> int:
    """Remove synthetic fixtures and demo sources left over from a demo-mode run."""
    async with db.sessions() as session:
        demo = select(MatchExternalRef.match_id).where(MatchExternalRef.provider == DEMO_PROVIDER)
        real = select(MatchExternalRef.match_id).where(MatchExternalRef.provider != DEMO_PROVIDER)
        result = await session.execute(delete(Match).where(Match.id.in_(demo), Match.id.not_in(real)))
        await session.execute(delete(Source).where(Source.key.in_(DEMO_SOURCES)))
        await session.commit()
        if result.rowcount:
            log.info("removed %s demo matches", result.rowcount)
        return result.rowcount or 0


class Engine:
    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db
        self.guard = URLGuard(settings.allowed_ports, settings.allow_hosts)
        self.fixtures_http = httpx.AsyncClient(timeout=20, headers={"User-Agent": settings.resolver_user_agent})
        self.checker_http = httpx.AsyncClient(
            timeout=settings.resolver_timeout_seconds,
            trust_env=False,  # proxies would hide the real peer address from the SSRF guard
            headers={
                "User-Agent": settings.resolver_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            },
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
        self.resolver = LinkResolver(self.checker_http, self.guard, settings.resolver_max_redirects,
                                     settings.resolver_max_body_bytes)
        self.validator = LinkValidator(self.resolver)
        self.providers: list[FixtureProvider] = build_providers(settings)
        self.connectors: list[SourceConnector] = build_connectors(settings)
        policies = {c.key: CheckPolicy(c.offline_markers, c.geo_block_url_markers, c.unverifiable_errors)
                    for c in self.connectors}
        self.health = HealthChecker(db, self.validator, settings, policies)
        self.media = MediaService(db, settings, self.fixtures_http)
        self._locks = {name: asyncio.Lock() for name in ("fixtures", "discovery", "health")}
        self._next_discovery: dict[str, float] = {}
        self._tasks: list[asyncio.Task] = []

    # ---- lifecycle -------------------------------------------------------------------
    async def bootstrap(self) -> None:
        await self.db.create_all()
        async with self.db.sessions() as session:
            await seed_reference_data(session)
            await sync_sources(session, self.connectors)
        if not self.settings.demo_mode:
            await purge_demo_data(self.db)
        if not self.settings.scheduler_enabled:
            # Without the scheduler (tests, one-off scripts) sync once up front. Otherwise the
            # fixtures loop starts immediately and the API serves whatever is already stored.
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self.sync_fixtures(), timeout=60)

    def start(self) -> None:
        for provider in self.providers:
            self._tasks.append(asyncio.create_task(self._fixtures_loop(provider), name=f"fixtures:{provider.key}"))
        self._tasks.append(asyncio.create_task(self._discovery_loop(), name="discovery"))
        self._tasks.append(asyncio.create_task(self._health_loop(), name="health"))
        self._tasks.append(asyncio.create_task(self._maintenance_loop(), name="maintenance"))
        if self.settings.media_enabled and not self.settings.demo_mode:
            self._tasks.append(asyncio.create_task(self.media.run_forever(), name="media"))

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()
        await self.fixtures_http.aclose()
        await self.checker_http.aclose()

    # ---- jobs (also used by the admin API) -----------------------------------------------
    async def sync_fixtures(self, provider: FixtureProvider | None = None) -> list[dict]:
        async with self._locks["fixtures"]:
            targets = [provider] if provider else self.providers
            return [await sync_provider(self.db, p, self.fixtures_http) for p in targets]

    async def run_sources(self, keys: list[str] | None = None) -> list[dict]:
        targets = [c for c in self.connectors if not keys or c.key in keys]
        async with self._locks["discovery"]:
            results = await asyncio.gather(
                *(run_connector(self.db, c, self.checker_http, self.guard, self.settings) for c in targets)
            )
        # Freshly discovered links have never been checked, so they are due immediately.
        await self.validate_links()
        return list(results)

    async def validate_links(self, link_ids: list[int] | None = None, force: bool = False) -> dict:
        async with self._locks["health"]:
            started = utcnow()
            summary = await self.health.run_cycle(link_ids=link_ids, force=force)
            if summary.get("checked"):
                async with self.db.sessions() as session:
                    run = await start_run(session, "health", None)
                    run.started_at = started
                    run.items_found = summary["checked"]
                    run.details = json.dumps(summary)
                    finish_run(run)
                    await session.commit()
            return summary

    # ---- loops ---------------------------------------------------------------------------
    async def _has_live(self) -> bool:
        async with self.db.sessions() as session:
            count = await session.scalar(select(func.count(Match.id)).where(Match.status.in_(LIVE_STATUSES)))
            return bool(count)

    async def _discovery_interval(self) -> int:
        now = utcnow()
        async with self.db.sessions() as session:
            hot = await session.scalar(
                select(func.count(Match.id)).where(
                    (Match.status.in_(LIVE_STATUSES))
                    | (Match.kickoff_time.between(now, now + timedelta(minutes=30)) & (Match.status == MatchStatus.SCHEDULED))
                )
            )
            if hot:
                return self.settings.discovery_hot_interval
            warm = await session.scalar(
                select(func.count(Match.id)).where(Match.kickoff_time.between(now, now + timedelta(hours=3)))
            )
        return self.settings.discovery_warm_interval if warm else self.settings.discovery_cold_interval

    async def _fixtures_loop(self, provider: FixtureProvider) -> None:
        while True:
            try:
                await self.sync_fixtures(provider)
                interval = provider.next_interval(self.settings, await self._has_live())
            except Exception:
                log.exception("fixture loop error (%s)", provider.key)
                interval = 60
            await asyncio.sleep(interval)

    async def _discovery_loop(self) -> None:
        await asyncio.sleep(2)  # let the HTTP server come up (demo sources are served by this process)
        loop = asyncio.get_running_loop()
        while True:
            try:
                now = loop.time()
                due = [c.key for c in self.connectors if self._next_discovery.get(c.key, 0) <= now]
                if due:
                    interval = await self._discovery_interval()
                    await self.run_sources(due)
                    for key in due:
                        self._next_discovery[key] = loop.time() + interval
            except Exception:
                log.exception("discovery loop error")
            await asyncio.sleep(self.settings.discovery_tick)

    async def _health_loop(self) -> None:
        await asyncio.sleep(3)
        while True:
            try:
                await self.validate_links()
            except Exception:
                log.exception("health loop error")
            await asyncio.sleep(self.settings.health_tick)

    async def _maintenance_loop(self) -> None:
        while True:
            await asyncio.sleep(3600)
            try:
                pruned = await prune_health_checks(self.db)
                async with self.db.sessions() as session:
                    await session.execute(delete(CrawlRun).where(CrawlRun.started_at < utcnow() - timedelta(days=3)))
                    await session.commit()
                log.info("maintenance: pruned %s health checks", pruned)
            except Exception:
                log.exception("maintenance loop error")
