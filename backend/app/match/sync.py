"""Fixture sync: provider fixtures -> normalized, de-duplicated matches."""

import logging
from collections import defaultdict
from datetime import timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Competition, Match, MatchExternalRef
from app.database.runs import finish_run, start_run
from app.database.session import Database
from app.match.providers.base import CompetitionRef, FixtureProvider, NormalizedFixture
from app.match.teams import TeamDirectory
from app.utils.text import sanitize_text, slugify
from app.utils.time import utcnow

log = logging.getLogger(__name__)
DEDUPE_WINDOW = timedelta(hours=36)


class FixtureSyncer:
    def __init__(self, session: AsyncSession, directory: TeamDirectory, provider_key: str):
        self.session = session
        self.directory = directory
        self.provider_key = provider_key
        self.comps_by_code: dict[str, Competition] = {}
        self.comps_by_slug: dict[str, Competition] = {}
        self.refs: dict[str, Match] = {}
        self.by_pair: dict[tuple[int, int], list[Match]] = defaultdict(list)
        self.owned: set[int] = set()
        self.slugs: set[str] = set()

    async def prepare(self, fixtures: list[NormalizedFixture]) -> None:
        for comp in (await self.session.scalars(select(Competition))).all():
            self.comps_by_slug[comp.slug] = comp
            if comp.code:
                self.comps_by_code[comp.code] = comp
        refs = await self.session.execute(
            select(MatchExternalRef.external_id, Match)
            .join(Match, Match.id == MatchExternalRef.match_id)
            .where(MatchExternalRef.provider == self.provider_key)
        )
        self.refs = {ext_id: match for ext_id, match in refs.all()}
        self.owned = {id(m) for m in self.refs.values()}  # matches this provider already has an event for
        if fixtures:
            lo = min(f.kickoff for f in fixtures) - DEDUPE_WINDOW
            hi = max(f.kickoff for f in fixtures) + DEDUPE_WINDOW
            for match in (await self.session.scalars(select(Match).where(Match.kickoff_time.between(lo, hi)))).all():
                self.by_pair[(match.home_team_id, match.away_team_id)].append(match)
        self.slugs = set((await self.session.scalars(select(Match.slug))).all())

    @staticmethod
    def _refresh(comp: Competition, ref: CompetitionRef) -> Competition:
        if ref.logo_url and not comp.logo_url and ref.logo_url.startswith("https://"):
            comp.logo_url = ref.logo_url
        if ref.espn_league and comp.espn_league != ref.espn_league:
            comp.espn_league = ref.espn_league
        if bool(comp.national_teams) != ref.national_teams and (ref.national_teams or ref.espn_league):
            comp.national_teams = ref.national_teams
        return comp

    def competition_for(self, ref: CompetitionRef) -> Competition:
        if ref.code and ref.code in self.comps_by_code:
            return self._refresh(self.comps_by_code[ref.code], ref)
        slug = slugify(ref.name)
        if slug in self.comps_by_slug:
            comp = self.comps_by_slug[slug]
            if not comp.is_major and ref.priority is not None:
                comp.priority = ref.priority
            return self._refresh(comp, ref)
        comp = Competition(
            slug=slug,
            code=ref.code if ref.code and ref.code not in self.comps_by_code else None,
            name=sanitize_text(ref.name, 120) or "Other",
            country=sanitize_text(ref.country, 80),
            logo_url=ref.logo_url if ref.logo_url and ref.logo_url.startswith("https://") else None,
            priority=ref.priority if ref.priority is not None else 10,
            is_major=False,
            national_teams=ref.national_teams,
            espn_league=ref.espn_league,
        )
        self.session.add(comp)
        self.comps_by_slug[slug] = comp
        if comp.code:
            self.comps_by_code[comp.code] = comp
        return comp

    def unique_slug(self, base: str) -> str:
        slug, n = base, 2
        while slug in self.slugs:
            slug, n = f"{base}-{n}", n + 1
        self.slugs.add(slug)
        return slug

    async def upsert(self, f: NormalizedFixture) -> Match:
        match = self.refs.get(f.external_id)
        if match is None:
            home = await self.directory.resolve_or_create(self.session, f.home, self.provider_key)
            away = await self.directory.resolve_or_create(self.session, f.away, self.provider_key)
            # Same pairing within the dedupe window from *another* provider = same match. Two
            # events from this provider are always two matches (league + cup meeting in a week).
            match = next(
                (
                    m
                    for m in self.by_pair[(home.id, away.id)]
                    if id(m) not in self.owned and abs(m.kickoff_time - f.kickoff) <= DEDUPE_WINDOW
                ),
                None,
            )
            if match is None:
                match = Match(
                    slug=self.unique_slug(f"{home.slug}-vs-{away.slug}-{f.kickoff:%Y-%m-%d}"),
                    home_team_id=home.id,
                    away_team_id=away.id,
                    kickoff_time=f.kickoff,
                )
                self.session.add(match)
                self.by_pair[(home.id, away.id)].append(match)
            await self.session.flush()
            self.session.add(MatchExternalRef(match_id=match.id, provider=self.provider_key, external_id=f.external_id))
            self.refs[f.external_id] = match
            self.owned.add(id(match))

        comp = self.competition_for(f.competition)
        if comp.id is None:
            await self.session.flush()
        match.competition_id = comp.id
        match.kickoff_time = f.kickoff
        match.status = f.status
        match.score_home, match.score_away = f.score_home, f.score_away
        match.minute, match.minute_display = f.minute, f.minute_display
        if f.venue:
            match.venue = sanitize_text(f.venue, 160)
        if f.referee:
            match.referee = sanitize_text(f.referee, 120)
        match.last_synced_at = utcnow()
        return match


STALE_LIVE_AFTER = timedelta(hours=5)


async def sync_provider(db: Database, provider: FixtureProvider, http: httpx.AsyncClient) -> dict:
    now = utcnow()
    try:
        fixtures = await provider.fetch(http, now)
    except Exception as exc:  # one provider failing must never stop the others
        log.warning("fixture provider %s failed: %s", provider.key, exc)
        code = "TIMEOUT" if isinstance(exc, httpx.TimeoutException) else "PROVIDER_ERROR"
        async with db.sessions() as session:
            run = await start_run(session, "fixtures", provider.key)
            run.started_at = now
            finish_run(run, "error", f"{type(exc).__name__}: {exc}", code)
            await session.commit()
        return {"provider": provider.key, "status": "error", "error": str(exc)}

    async with db.sessions() as session:
        live = 0
        if fixtures:  # pollers often have nothing due; don't log empty runs
            run = await start_run(session, "fixtures", provider.key)
            run.started_at = now
            directory = await TeamDirectory.load(session)
            syncer = FixtureSyncer(session, directory, provider.key)
            await syncer.prepare(fixtures)
            for fixture in fixtures:
                await syncer.upsert(fixture)
                live += fixture.status in ("live", "halftime")
            run.items_found = run.matched = len(fixtures)
            finish_run(run)
        # A match the feed stopped updating must not stay "live" forever.
        await session.execute(
            update(Match)
            .where(Match.status.in_(("live", "halftime")), Match.kickoff_time < now - STALE_LIVE_AFTER)
            .values(status="finished", minute_display="FT")
        )
        await session.commit()
    return {"provider": provider.key, "status": "ok", "fixtures": len(fixtures), "live": live}
