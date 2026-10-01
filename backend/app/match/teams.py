import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Team, TeamAlias, TeamExternalRef
from app.database.seed_data import TEAM_POPULARITY
from app.match.normalize import name_similarity, normalize_name
from app.match.providers.base import TeamRef
from app.utils.text import sanitize_text, slugify

log = logging.getLogger(__name__)
_POPULARITY = {normalize_name(name): score for name, score in TEAM_POPULARITY.items()}


class TeamDirectory:
    """In-memory index of every team and its known name forms."""

    def __init__(self, teams: list[Team], aliases: list[TeamAlias], refs: list[TeamExternalRef] | None = None):
        self.teams: dict[int, Team] = {t.id: t for t in teams}
        self.external: dict[tuple[str, str], int] = {(r.provider, r.external_id): r.team_id for r in refs or []}
        self.slugs: set[str] = {t.slug for t in teams}
        self.alias_to_team: dict[str, int] = {}
        self.forms: dict[int, set[str]] = {t.id: set() for t in teams}
        for team in teams:
            for raw in (team.name, team.short_name):
                if raw:
                    self.forms[team.id].add(normalize_name(raw))
            if team.tla:
                self.forms[team.id].add(team.tla.lower())
        for alias in aliases:
            self.alias_to_team[alias.alias] = alias.team_id
            self.forms.setdefault(alias.team_id, set()).add(alias.alias)

    @classmethod
    async def load(cls, session: AsyncSession) -> "TeamDirectory":
        teams = list((await session.scalars(select(Team))).all())
        aliases = list((await session.scalars(select(TeamAlias))).all())
        refs = list((await session.scalars(select(TeamExternalRef))).all())
        return cls(teams, aliases, refs)

    def lookup_name(self, *names: str | None) -> Team | None:
        """Exact lookup by full or short name. TLAs are deliberately excluded here:
        three-letter codes collide across leagues (FCB = Bayern, Basel, Barcelona...)."""
        for raw in names:
            if not raw:
                continue
            team_id = self.alias_to_team.get(normalize_name(raw))
            if team_id is not None:
                return self.teams[team_id]
        return None

    def similarity(self, raw_name: str, team_id: int) -> float:
        return name_similarity(normalize_name(raw_name), self.forms.get(team_id, set()))

    async def resolve_or_create(self, session: AsyncSession, ref: TeamRef, provider: str | None = None) -> Team:
        team: Team | None = None
        ext_key = (provider, ref.external_id) if provider and ref.external_id else None
        if ext_key and ext_key in self.external:
            team = self.teams.get(self.external[ext_key])
        if team is None:
            team = self.lookup_name(ref.name, ref.short_name)
            # Same name in a different country is a different club (two clubs called Nacional).
            if team and ref.country and team.country and normalize_name(ref.country) != normalize_name(team.country):
                team = None
        if team is None:
            team = await self._create(session, ref)
        if ext_key and ext_key not in self.external:
            session.add(TeamExternalRef(team_id=team.id, provider=provider, external_id=ref.external_id))
            self.external[ext_key] = team.id
        # Fill gaps from the provider; never overwrite curated values.
        if ref.logo_url and not team.logo_url and ref.logo_url.startswith("https://"):
            team.logo_url = ref.logo_url
        if ref.primary_color and not team.primary_color:
            team.primary_color = ref.primary_color
        if ref.secondary_color and not team.secondary_color:
            team.secondary_color = ref.secondary_color
        if not team.popularity:
            team.popularity = _POPULARITY.get(normalize_name(team.name), 0)
        return team

    async def _create(self, session: AsyncSession, ref: TeamRef) -> Team:
        name = sanitize_text(ref.name, 120) or "Unknown"
        slug = base = slugify(name)
        n = 2
        while slug in self.slugs:
            slug, n = f"{base}-{n}", n + 1
        team = Team(
            slug=slug,
            name=name,
            short_name=sanitize_text(ref.short_name, 60),
            tla=(sanitize_text(ref.tla, 5) or None),
            country=sanitize_text(ref.country, 80),
        )
        session.add(team)
        await session.flush()
        self.teams[team.id] = team
        self.slugs.add(slug)
        self.forms[team.id] = set()
        for raw in (team.name, team.short_name, team.tla):
            if raw:
                await self.add_alias(session, team.id, raw)
        log.info("created team %s (%s)", team.name, team.slug)
        return team

    async def add_alias(self, session: AsyncSession, team_id: int, raw: str) -> bool:
        alias = normalize_name(raw)
        self.forms.setdefault(team_id, set()).add(alias)
        if not alias or alias in self.alias_to_team:
            return False
        session.add(TeamAlias(team_id=team_id, alias=alias))
        self.alias_to_team[alias] = team_id
        return True
