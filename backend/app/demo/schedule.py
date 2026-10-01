"""Deterministic synthetic fixture schedule for demo mode.

Kick-offs sit on a fixed 45-minute grid anchored to a constant epoch, so the same
match always has the same identity across restarts, and at any time of day there
are a few live games, some finished ones and a steady stream of upcoming ones.
Each competition runs a round-robin, so a club never plays twice in one round.
"""

import hashlib
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from app.database.seed_data import COMPETITION_TEAMS, TEAMS

ANCHOR = datetime(2026, 1, 1, tzinfo=timezone.utc)
SLOT = timedelta(minutes=45)
COMP_CYCLE = ["PL", "PD", "CL", "BL1", "SA", "PL", "FL1", "PD", "EL", "SA", "MLS", "BL1"]
HALF_TIME_BREAK = 15

_TEAM_INFO = {t[0]: t for t in TEAMS}


def _popularity(slug: str) -> int:
    return _TEAM_INFO[slug][7]


def _rng(*parts: object) -> random.Random:
    seed = hashlib.sha256("|".join(map(str, ("ubf-demo", *parts))).encode()).hexdigest()
    return random.Random(int(seed[:16], 16))


def _poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _round_robin_pair(teams: list[str], index: int) -> tuple[str, str]:
    n = len(teams)
    per_round = n // 2
    rnd, pair = divmod(index, per_round)
    rnd_in_cycle = rnd % (n - 1)
    rotating = teams[1:]
    rotating = rotating[rnd_in_cycle:] + rotating[:rnd_in_cycle]
    order = [teams[0], *rotating]
    a, b = order[pair], order[n - 1 - pair]
    # Alternate home advantage by round, and flip the whole schedule every other cycle.
    if (rnd + pair + (rnd // (n - 1))) % 2:
        a, b = b, a
    return a, b


@dataclass(frozen=True)
class MatchState:
    status: str
    minute: int | None
    minute_display: str | None
    score_home: int | None
    score_away: int | None


@dataclass(frozen=True)
class DemoMatch:
    slot: int
    competition: str
    home: str
    away: str
    kickoff: datetime
    stoppage_first: int
    stoppage_second: int
    goals: tuple[tuple[float, str], ...]  # (elapsed real minutes, "home"|"away")

    @property
    def external_id(self) -> str:
        return f"demo-{self.slot}"

    @property
    def duration(self) -> float:
        return 45 + self.stoppage_first + HALF_TIME_BREAK + 45 + self.stoppage_second

    def state_at(self, now: datetime) -> MatchState:
        elapsed = (now - self.kickoff).total_seconds() / 60
        if elapsed < 0:
            return MatchState("scheduled", None, None, None, None)
        home = sum(1 for at, side in self.goals if at <= elapsed and side == "home")
        away = sum(1 for at, side in self.goals if at <= elapsed and side == "away")
        first_end = 45 + self.stoppage_first
        second_start = first_end + HALF_TIME_BREAK
        if elapsed >= self.duration:
            return MatchState("finished", 90, "FT", home, away)
        if elapsed < first_end:
            minute = int(elapsed) + 1
            display = f"{minute}'" if minute <= 45 else f"45+{minute - 45}'"
            return MatchState("live", min(minute, 45), display, home, away)
        if elapsed < second_start:
            return MatchState("halftime", 45, "HT", home, away)
        minute = 46 + int(elapsed - second_start)
        display = f"{minute}'" if minute <= 90 else f"90+{minute - 90}'"
        return MatchState("live", min(minute, 90), display, home, away)


def _comp_index(slot: int, comp: str) -> int:
    """How many earlier slots in the cycle belonged to the same competition."""
    per_cycle = COMP_CYCLE.count(comp)
    cycle, pos = divmod(slot, len(COMP_CYCLE))
    return cycle * per_cycle + COMP_CYCLE[:pos].count(comp)


@lru_cache(maxsize=4096)
def match_for_slot(slot: int) -> DemoMatch:
    comp = COMP_CYCLE[slot % len(COMP_CYCLE)]
    home, away = _round_robin_pair(COMPETITION_TEAMS[comp], _comp_index(slot, comp))
    rng = _rng(slot, home, away)
    s1, s2 = rng.randint(1, 4), rng.randint(2, 6)
    diff = (_popularity(home) - _popularity(away)) / 40
    lam_home = min(max(1.35 + diff, 0.35), 3.0)
    lam_away = min(max(1.05 - diff, 0.3), 2.6)
    first_end = 45 + s1
    playing = first_end + 45 + s2

    def goal_time() -> float:
        # Sample playing time, then shift second-half goals past the break.
        t = rng.uniform(0.5, playing - 0.5)
        return t if t < first_end else t + HALF_TIME_BREAK

    goals = [(goal_time(), "home") for _ in range(_poisson(rng, lam_home))]
    goals += [(goal_time(), "away") for _ in range(_poisson(rng, lam_away))]
    goals.sort()
    return DemoMatch(
        slot=slot,
        competition=comp,
        home=home,
        away=away,
        kickoff=ANCHOR + SLOT * slot,
        stoppage_first=s1,
        stoppage_second=s2,
        goals=tuple(goals),
    )


def matches_between(start: datetime, end: datetime) -> list[DemoMatch]:
    first = max(0, math.ceil((start - ANCHOR) / SLOT))
    last = math.floor((end - ANCHOR) / SLOT)
    return [match_for_slot(s) for s in range(first, last + 1)]


def schedule_window(now: datetime) -> list[DemoMatch]:
    return matches_between(now - timedelta(hours=30), now + timedelta(days=7))
