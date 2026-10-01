from datetime import datetime, timedelta

import httpx

from app.config import Settings
from app.match.providers.base import CompetitionRef, FixtureProvider, NormalizedFixture, TeamRef

API_URL = "https://api.football-data.org/v4/matches"

_STATUS = {
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    "IN_PLAY": "live",
    "PAUSED": "halftime",
    "FINISHED": "finished",
    "AWARDED": "finished",
    "POSTPONED": "postponed",
    "SUSPENDED": "suspended",
    "CANCELLED": "cancelled",
}


def _team(raw: dict) -> TeamRef:
    return TeamRef(
        name=raw.get("name") or raw.get("shortName") or "Unknown",
        short_name=raw.get("shortName"),
        tla=raw.get("tla"),
        logo_url=raw.get("crest"),
    )


class FootballDataProvider(FixtureProvider):
    """Official football-data.org v4 API. Enabled when UBF_FOOTBALL_DATA_API_KEY is set.

    The free tier allows 10 requests/minute and covers the major European leagues
    and the Champions League; one request covers the whole date window.
    """

    key = "football-data"
    name = "football-data.org"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @classmethod
    def enabled(cls, settings: Settings) -> bool:
        return bool(settings.football_data_api_key)

    def next_interval(self, settings: Settings, has_live: bool) -> int:
        return max(60, settings.fixtures_live_interval) if has_live else settings.fixtures_idle_interval

    async def fetch(self, http: httpx.AsyncClient, now: datetime) -> list[NormalizedFixture]:
        params = {
            "dateFrom": (now - timedelta(days=1)).date().isoformat(),
            "dateTo": (now + timedelta(days=7)).date().isoformat(),  # API maximum range is 10 days
        }
        response = await http.get(API_URL, params=params, headers={"X-Auth-Token": self.api_key}, timeout=20)
        response.raise_for_status()
        fixtures = []
        for m in response.json().get("matches", []):
            comp = m.get("competition") or {}
            area = m.get("area") or {}
            score = (m.get("score") or {}).get("fullTime") or {}
            status = _STATUS.get(m.get("status", ""), "scheduled")
            minute = m.get("minute")
            injury = m.get("injuryTime")
            display = None
            if status == "halftime":
                display = "HT"
            elif status == "finished":
                display = "FT"
            elif status == "live" and minute:
                display = f"{minute}+{injury}'" if injury else f"{minute}'"
            referee = next((r.get("name") for r in m.get("referees", []) if r.get("type") == "REFEREE"), None)
            fixtures.append(
                NormalizedFixture(
                    provider=self.key,
                    external_id=str(m["id"]),
                    home=_team(m.get("homeTeam") or {}),
                    away=_team(m.get("awayTeam") or {}),
                    competition=CompetitionRef(
                        name=comp.get("name") or "Other",
                        code=comp.get("code"),
                        country=area.get("name"),
                        logo_url=comp.get("emblem"),
                    ),
                    kickoff=datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")),
                    status=status,
                    score_home=score.get("home"),
                    score_away=score.get("away"),
                    minute=int(minute) if isinstance(minute, (int, str)) and str(minute).isdigit() else None,
                    minute_display=display,
                    venue=m.get("venue"),
                    referee=referee,
                )
            )
        return fixtures
