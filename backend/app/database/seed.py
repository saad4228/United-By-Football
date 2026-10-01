import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Competition, Team, TeamAlias
from app.database.seed_data import COMPETITIONS, TEAM_LOGOS, TEAM_POPULARITY, TEAMS
from app.match.normalize import normalize_name

log = logging.getLogger(__name__)


async def seed_reference_data(session: AsyncSession) -> None:
    """Idempotently insert competitions, clubs and their aliases."""
    existing_comps = {c.slug: c for c in (await session.scalars(select(Competition))).all()}
    for slug, code, name, short, country, priority, _aliases in COMPETITIONS:
        comp = existing_comps.get(slug)
        if comp is None:
            comp = Competition(slug=slug, code=code)
            session.add(comp)
        comp.name, comp.short_name, comp.country = name, short, country
        comp.priority, comp.is_major = priority, True

    existing_teams = {t.slug: t for t in (await session.scalars(select(Team))).all()}
    taken = {a.alias: a.team_id for a in (await session.scalars(select(TeamAlias))).all()}
    for slug, name, short, tla, country, primary, secondary, popularity, _venue, aliases in TEAMS:
        team = existing_teams.get(slug)
        if team is None:
            team = Team(slug=slug)
            session.add(team)
        team.name, team.short_name, team.tla, team.country = name, short, tla, country
        team.primary_color, team.secondary_color, team.popularity = primary, secondary, popularity
        team.logo_url = TEAM_LOGOS.get(slug, team.logo_url)
        await session.flush()
        for raw in (name, short, tla, *aliases):
            alias = normalize_name(raw)
            if alias in taken:
                if taken[alias] != team.id:
                    log.debug("alias %r already belongs to team %s", alias, taken[alias])
                continue
            session.add(TeamAlias(team_id=team.id, alias=alias))
            taken[alias] = team.id

    # Teams that arrived from fixture feeds before the popularity table knew them.
    known = {normalize_name(name): score for name, score in TEAM_POPULARITY.items()}
    for team in (await session.scalars(select(Team).where(Team.popularity == 0))).all():
        team.popularity = known.get(normalize_name(team.name), 0)
    await session.commit()
