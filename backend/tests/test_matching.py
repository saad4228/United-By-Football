from datetime import datetime, timedelta, timezone

import pytest

from app.match.matcher import MatchCandidate, MatchIndex
from app.match.providers.base import CompetitionRef, NormalizedFixture, TeamRef
from app.match.sync import FixtureSyncer
from app.match.teams import TeamDirectory

KICKOFF = datetime(2026, 10, 4, 16, 30, tzinfo=timezone.utc)


@pytest.fixture
async def directory(app):
    async with app.state.db.sessions() as session:
        yield await TeamDirectory.load(session)


def team_id(directory: TeamDirectory, slug: str) -> int:
    return next(t.id for t in directory.teams.values() if t.slug == slug)


def index_with(directory, *pairs):
    candidates = [
        MatchCandidate(i + 1, team_id(directory, h), team_id(directory, a), KICKOFF + timedelta(minutes=15 * i), code)
        for i, (h, a, code) in enumerate(pairs)
    ]
    return MatchIndex(directory, candidates)


@pytest.mark.parametrize(
    ("home", "away"),
    [("Man City", "Arsenal"), ("MCI", "ARS"), ("Manchester City FC", "Arsenal FC"), ("Man. City", "The Gunners")],
)
async def test_naming_variants_map_to_one_match(directory, home, away):
    index = index_with(directory, ("manchester-city", "arsenal", "PL"), ("manchester-united", "chelsea", "PL"))
    result = index.find(home, away, now=KICKOFF, kickoff=KICKOFF)
    assert result is not None and result.match_id == 1


async def test_swapped_order_still_matches(directory):
    index = index_with(directory, ("manchester-city", "arsenal", "PL"))
    result = index.find("Arsenal", "Man City", now=KICKOFF, kickoff=KICKOFF)
    assert result is not None and result.swapped


async def test_united_listing_does_not_match_city_fixture(directory):
    index = index_with(directory, ("manchester-city", "arsenal", "PL"))
    assert index.find("Man Utd", "Arsenal", now=KICKOFF, kickoff=KICKOFF) is None


async def test_kickoff_far_away_is_rejected(directory):
    index = index_with(directory, ("manchester-city", "arsenal", "PL"))
    assert index.find("Man City", "Arsenal", now=KICKOFF, kickoff=KICKOFF + timedelta(days=2)) is None


async def test_unknown_teams_are_not_invented(directory):
    index = index_with(directory, ("manchester-city", "arsenal", "PL"))
    assert index.find("Northfield Rovers", "Eastbrook Athletic", now=KICKOFF) is None


async def test_duplicate_fixtures_from_two_providers_merge(app):
    def fixture(provider, ext, home, away, minutes):
        return NormalizedFixture(provider=provider, external_id=ext, home=TeamRef(home), away=TeamRef(away),
                                 competition=CompetitionRef("Premier League", "PL"),
                                 kickoff=KICKOFF + timedelta(minutes=minutes), status="scheduled")

    async with app.state.db.sessions() as session:
        directory = await TeamDirectory.load(session)
        first = [fixture("provider-a", "1", "Manchester City FC", "Arsenal FC", 0)]
        a = FixtureSyncer(session, directory, "provider-a")
        await a.prepare(first)
        m1 = await a.upsert(first[0])
        await session.commit()

        second = [fixture("provider-b", "xyz", "Man City", "Arsenal", 5)]
        b = FixtureSyncer(session, directory, "provider-b")
        await b.prepare(second)
        m2 = await b.upsert(second[0])
        await session.commit()

        assert m1.id == m2.id
        await session.refresh(m1, ["external_refs"])
        assert {r.provider for r in m1.external_refs} == {"provider-a", "provider-b"}
