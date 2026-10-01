"""Associates a source's free-text fixture description with a match in the database.

A listing such as "MCI v ARS 20:00" is scored against every match in a time window
using team identity (aliases, abbreviations, fuzzy similarity), kickoff proximity
and an optional competition hint. Both teams must match independently, which keeps
"Man City" from ever being merged with "Man United".
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Competition, Match
from app.database.seed_data import COMPETITIONS
from app.match.normalize import name_similarity, normalize_name
from app.match.teams import TeamDirectory

TEAM_THRESHOLD = 0.80
KICKOFF_TOLERANCE = timedelta(hours=3)

_COMP_FORMS: dict[str, set[str]] = {
    code: {normalize_name(n) for n in (name, short, *aliases)} | {code.lower()}
    for _, code, name, short, _, _, aliases in COMPETITIONS
}


@dataclass(frozen=True)
class MatchCandidate:
    id: int
    home_id: int
    away_id: int
    kickoff: datetime
    competition_code: str | None


@dataclass(frozen=True)
class MatchResult:
    match_id: int
    score: float
    swapped: bool


class MatchIndex:
    def __init__(self, directory: TeamDirectory, candidates: list[MatchCandidate]):
        self.directory = directory
        self.candidates = candidates

    @classmethod
    async def load(cls, session: AsyncSession, directory: TeamDirectory, now: datetime) -> "MatchIndex":
        rows = await session.execute(
            select(Match.id, Match.home_team_id, Match.away_team_id, Match.kickoff_time, Competition.code)
            .outerjoin(Competition, Competition.id == Match.competition_id)
            .where(Match.kickoff_time >= now - timedelta(hours=8), Match.kickoff_time <= now + timedelta(days=8))
        )
        return cls(directory, [MatchCandidate(*row) for row in rows.all()])

    def find(
        self,
        home: str,
        away: str,
        now: datetime,
        kickoff: datetime | None = None,
        competition: str | None = None,
    ) -> MatchResult | None:
        comp_norm = normalize_name(competition) if competition else None
        best: MatchResult | None = None
        best_score = 0.0
        for c in self.candidates:
            if kickoff is not None:
                delta = abs(c.kickoff - kickoff)
                if delta > KICKOFF_TOLERANCE:
                    continue
                time_bonus = 0.05 * (1 - delta / KICKOFF_TOLERANCE)
            else:
                # No time given: only consider matches that are live or about to start.
                if not (now - timedelta(hours=3) <= c.kickoff <= now + timedelta(hours=36)):
                    continue
                time_bonus = 0.0

            direct = min(self.directory.similarity(home, c.home_id), self.directory.similarity(away, c.away_id))
            swapped = min(self.directory.similarity(home, c.away_id), self.directory.similarity(away, c.home_id))
            is_swapped = swapped > direct
            team_score = max(direct, swapped * 0.97)
            if team_score < TEAM_THRESHOLD:
                continue

            comp_bonus = 0.0
            if comp_norm and c.competition_code in _COMP_FORMS:
                forms = _COMP_FORMS[c.competition_code]
                comp_bonus = 0.03 if name_similarity(comp_norm, forms) >= 0.85 else -0.05

            score = team_score + time_bonus + comp_bonus
            if score > best_score:
                best_score = score
                best = MatchResult(c.id, round(score, 3), is_swapped)
        return best
