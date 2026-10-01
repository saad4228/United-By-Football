from datetime import datetime

import httpx

from app.config import Settings
from app.database.seed_data import COMPETITIONS, TEAMS
from app.demo.schedule import schedule_window
from app.match.providers.base import CompetitionRef, FixtureProvider, NormalizedFixture, TeamRef

_TEAMS = {t[0]: t for t in TEAMS}
_COMPS = {c[1]: c for c in COMPETITIONS}


def _team_ref(slug: str) -> TeamRef:
    _, name, short, tla, country, *_ = _TEAMS[slug]
    return TeamRef(name=name, short_name=short, tla=tla, country=country)


class DemoFixtureProvider(FixtureProvider):
    """Synthetic, time-relative fixtures so the product always has something to show."""

    key = "demo-fixtures"
    name = "Demo fixtures"

    @classmethod
    def enabled(cls, settings: Settings) -> bool:
        return settings.demo_mode

    async def fetch(self, http: httpx.AsyncClient, now: datetime) -> list[NormalizedFixture]:
        fixtures = []
        for m in schedule_window(now):
            state = m.state_at(now)
            _, code, comp_name, _, country, *_ = _COMPS[m.competition]
            fixtures.append(
                NormalizedFixture(
                    provider=self.key,
                    external_id=m.external_id,
                    home=_team_ref(m.home),
                    away=_team_ref(m.away),
                    competition=CompetitionRef(name=comp_name, code=code, country=country),
                    kickoff=m.kickoff,
                    status=state.status,
                    score_home=state.score_home,
                    score_away=state.score_away,
                    minute=state.minute,
                    minute_display=state.minute_display,
                    venue=_TEAMS[m.home][8],
                )
            )
        return fixtures
