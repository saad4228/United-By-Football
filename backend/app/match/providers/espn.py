"""Real fixtures from ESPN's public soccer scoreboard (site.api.espn.com).

No API key. Each league's scoreboard carries its season calendar, so we only
request days that actually have fixtures. Cup-style competitions publish rounds
instead of days, so every day in the window is checked for those. Every
(league, day) page is cached with a TTL that depends on how live it is:

* a day with a match in progress or about to kick off: 30 s
* today / yesterday otherwise: 5 min
* future days: 60 min

So the provider can be polled every 30 s and only fetches what is due. This is
an undocumented public feed: fine for development, but use a licensed data
provider for production.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.config import Settings
from app.match.providers.base import CompetitionRef, FixtureProvider, NormalizedFixture, TeamRef

log = logging.getLogger(__name__)
BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
USER_AGENT = f"python-httpx/{httpx.__version__}"

DAY_TTL_HOT = 30
DAY_TTL_RECENT = 300
DAY_TTL_FUTURE = 3600
CALENDAR_TTL = 6 * 3600
WINDOW_PAST_DAYS = 1
# League calendars tell us the exact match days, so looking two weeks ahead is cheap and
# always includes each league's next round. Cups publish only rounds, so every day in their
# window is a request: keep that one to a week (their next match day comes with the calendar).
WINDOW_FUTURE_DAYS_LEAGUE = 14
WINDOW_FUTURE_DAYS_CUP = 7


@dataclass(frozen=True)
class League:
    code: str | None  # our competition code for the seeded majors
    country: str | None  # None for international/continental competitions
    priority: int
    women: bool = False
    national: bool = False  # national teams rather than clubs


LEAGUES: dict[str, League] = {
    "uefa.champions": League("CL", None, 100),
    "eng.1": League("PL", "England", 95),
    "esp.1": League("PD", "Spain", 90),
    "ger.1": League("BL1", "Germany", 85),
    "ita.1": League("SA", "Italy", 85),
    "fra.1": League("FL1", "France", 80),
    "uefa.europa": League("EL", None, 75),
    "usa.1": League("MLS", "USA", 70),
    "uefa.nations": League(None, None, 82, national=True),
    "conmebol.libertadores": League(None, None, 72),
    "uefa.europa.conf": League(None, None, 65),
    "concacaf.nations.league": League(None, None, 62, national=True),
    "fifa.friendly": League(None, None, 60, national=True),
    "conmebol.sudamericana": League(None, None, 58),
    "por.1": League(None, "Portugal", 58),
    "bra.1": League(None, "Brazil", 58),
    "ned.1": League(None, "Netherlands", 55),
    "arg.1": League(None, "Argentina", 55),
    "afc.champions": League(None, None, 55),
    "eng.2": League(None, "England", 50),
    "tur.1": League(None, "Turkey", 50),
    "ksa.1": League(None, "Saudi Arabia", 50),
    "mex.1": League(None, "Mexico", 50),
    "sco.1": League(None, "Scotland", 45),
    "bel.1": League(None, "Belgium", 45),
    "ind.1": League(None, "India", 45),
    "eng.w.1": League(None, "England", 45, women=True),
    "ger.2": League(None, "Germany", 42),
    "esp.2": League(None, "Spain", 40),
    "ita.2": League(None, "Italy", 40),
    "jpn.1": League(None, "Japan", 40),
    "usa.nwsl": League(None, "USA", 40, women=True),
    "fra.2": League(None, "France", 38),
    "col.1": League(None, "Colombia", 35),
}

_FINISHED = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN", "STATUS_FINAL_ET"}
_POSTPONED = {"STATUS_POSTPONED"}
_CANCELLED = {"STATUS_CANCELED", "STATUS_CANCELLED"}
_SUSPENDED = {"STATUS_SUSPENDED", "STATUS_ABANDONED"}


def _hex(value: object) -> str | None:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 6 and all(c in "0123456789abcdefABCDEF" for c in text):
        return f"#{text.upper()}"
    return None


def _secure(url: object) -> str | None:
    """ESPN lists some assets as http://; its CDN serves the same files over https."""
    text = str(url or "")
    if text.startswith("http://") and ".espncdn.com/" in text:
        text = "https://" + text[len("http://"):]
    return text if text.startswith("https://") else None


def _score(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def map_status(status: dict) -> tuple[str, int | None, str | None]:
    """ESPN status block -> (our status, minute, display)."""
    kind = status.get("type") or {}
    name, state = kind.get("name", ""), kind.get("state", "")
    clock = status.get("clock") or 0
    if name in _POSTPONED:
        return "postponed", None, None
    if name in _CANCELLED:
        return "cancelled", None, None
    if name in _SUSPENDED:
        return "suspended", None, None
    if state == "in":
        if name == "STATUS_HALFTIME":
            return "halftime", 45, "HT"
        display = status.get("displayClock") or kind.get("shortDetail")
        return "live", int(clock // 60) or None, display
    if state == "post" or name in _FINISHED:
        detail = kind.get("shortDetail") or "FT"
        return "finished", 90, detail if len(detail) <= 8 else "FT"
    return "scheduled", None, None


def _team(raw: dict, league: League) -> TeamRef:
    team = raw.get("team") or {}
    name = team.get("displayName") or team.get("name") or "Unknown"
    short = team.get("shortDisplayName")
    if league.women:
        # ESPN names women's sides exactly like the men's clubs ("Manchester United").
        name = name if "women" in name.lower() else f"{name} Women"
        short = (short if "women" in short.lower() else f"{short} Women") if short else None
    return TeamRef(
        name=name,
        short_name=short,
        tla=team.get("abbreviation"),
        logo_url=_secure(team.get("logo")),
        country=league.country,
        external_id=f"{'w' if league.women else ''}{team.get('id')}" if team.get("id") else None,
        primary_color=_hex(team.get("color")),
        secondary_color=_hex(team.get("alternateColor")),
    )


def parse_scoreboard(payload: dict, slug: str, league: League, provider: str = "espn") -> list[NormalizedFixture]:
    lg = (payload.get("leagues") or [{}])[0]
    logo = _secure(next((l.get("href") for l in lg.get("logos", []) if "dark" not in (l.get("rel") or [])), None))
    comp = CompetitionRef(
        name=lg.get("name") or slug,
        code=league.code,
        country=league.country,
        logo_url=logo,
        priority=league.priority,
        national_teams=league.national,
        espn_league=slug,
    )
    fixtures = []
    for event in payload.get("events", []):
        try:
            competition = (event.get("competitions") or [{}])[0]
            sides = {c.get("homeAway"): c for c in competition.get("competitors", [])}
            if "home" not in sides or "away" not in sides:
                continue
            status, minute, display = map_status(competition.get("status") or event.get("status") or {})
            has_score = status in ("live", "halftime", "finished")
            kickoff = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
            fixtures.append(
                NormalizedFixture(
                    provider=provider,
                    external_id=str(event["id"]),
                    home=_team(sides["home"], league),
                    away=_team(sides["away"], league),
                    competition=comp,
                    kickoff=kickoff,
                    status=status,
                    score_home=_score(sides["home"].get("score")) if has_score else None,
                    score_away=_score(sides["away"].get("score")) if has_score else None,
                    minute=minute,
                    minute_display=display,
                    venue=(competition.get("venue") or {}).get("fullName"),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            log.debug("skipping malformed ESPN event in %s: %s", slug, exc)
    return fixtures


def _calendar_days(payload: dict) -> tuple[str, set[str] | None]:
    """('day', {YYYYMMDD,...}) for leagues with a match-day calendar, ('list', None) for cups."""
    lg = (payload.get("leagues") or [{}])[0]
    if lg.get("calendarType") != "day":
        return "list", None
    days = set()
    for entry in lg.get("calendar", []):
        stamp = entry if isinstance(entry, str) else (entry or {}).get("startDate")
        try:
            # Calendar stamps are US-Eastern midnights expressed in UTC (e.g. 07:00Z).
            moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00")) - timedelta(hours=5)
            days.add(moment.strftime("%Y%m%d"))
        except ValueError:
            continue
    return "day", days


def _is_hot(fixture: NormalizedFixture, now: datetime) -> bool:
    if fixture.status in ("live", "halftime"):
        return True
    return fixture.status == "scheduled" and now - timedelta(hours=3) <= fixture.kickoff <= now + timedelta(minutes=20)


class ESPNProvider(FixtureProvider):
    key = "espn"
    name = "ESPN scoreboard"

    def __init__(self, leagues: dict[str, League], concurrency: int = 6):
        self.leagues = leagues
        self.concurrency = concurrency
        self._calendars: dict[str, tuple[float, str, set[str] | None]] = {}
        self._fetched: dict[tuple[str, str], float] = {}
        self._hot: set[tuple[str, str]] = set()

    @classmethod
    def enabled(cls, settings: Settings) -> bool:
        return settings.espn_enabled and not settings.demo_mode

    @classmethod
    def from_settings(cls, settings: Settings) -> "ESPNProvider":
        slugs = [s.strip() for s in settings.espn_leagues.split(",") if s.strip()] or list(LEAGUES)
        return cls({s: LEAGUES.get(s, League(None, None, 30)) for s in slugs}, settings.espn_concurrency)

    def next_interval(self, settings: Settings, has_live: bool) -> int:
        # Polling is cheap: each call only fetches pages whose TTL has run out.
        return settings.fixtures_live_interval

    async def _get(self, http: httpx.AsyncClient, slug: str, day: str | None, sem: asyncio.Semaphore) -> dict | None:
        params = {"dates": day} if day else {}
        async with sem:
            try:
                # ESPN's edge rejects unrecognised custom agents but accepts standard HTTP-library
                # ones, so send httpx's own default identifier (never a browser string).
                response = await http.get(
                    f"{BASE_URL}/{slug}/scoreboard", params=params, timeout=15, headers={"User-Agent": USER_AGENT}
                )
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("ESPN %s %s failed: %s", slug, day or "default", exc)
                return None

    async def fetch(self, http: httpx.AsyncClient, now: datetime) -> list[NormalizedFixture]:
        mono = time.monotonic()
        sem = asyncio.Semaphore(self.concurrency)
        today = now.astimezone(timezone.utc).date()
        window = [(today + timedelta(days=d)).strftime("%Y%m%d") for d in range(-WINDOW_PAST_DAYS, WINDOW_FUTURE_DAYS_LEAGUE + 1)]
        cup_last = (today + timedelta(days=WINDOW_FUTURE_DAYS_CUP)).strftime("%Y%m%d")
        today_key = today.strftime("%Y%m%d")
        found: dict[str, NormalizedFixture] = {}
        attempted = failed = 0

        # 1. Calendars (also returns the league's current match day, so keep those events).
        stale = [s for s in self.leagues if mono - self._calendars.get(s, (-1e9, "", None))[0] >= CALENDAR_TTL]
        results = await asyncio.gather(*(self._get(http, s, None, sem) for s in stale))
        for slug, payload in zip(stale, results):
            attempted += 1
            if payload is None:
                failed += 1
                continue
            self._calendars[slug] = (mono, *_calendar_days(payload))
            for f in parse_scoreboard(payload, slug, self.leagues[slug]):
                found[f.external_id] = f

        # 2. Match days in the window whose cache has expired.
        jobs: list[tuple[str, str]] = []
        for slug in self.leagues:
            if slug not in self._calendars:
                continue
            _, kind, days = self._calendars[slug]
            if kind == "day" and days:
                # The last round before the window (rounds span ~3 match days), so every
                # league shows recent results even after an international break.
                for day in sorted(d for d in days if d < window[0])[-3:]:
                    if mono - self._fetched.get((slug, day), -1e9) >= CALENDAR_TTL:
                        jobs.append((slug, day))
            for day in window:
                if kind == "day" and days is not None and day not in days:
                    continue
                if kind != "day" and day > cup_last:
                    continue
                key = (slug, day)
                ttl = DAY_TTL_HOT if key in self._hot else DAY_TTL_RECENT if day <= today_key else DAY_TTL_FUTURE
                if mono - self._fetched.get(key, -1e9) >= ttl:
                    jobs.append(key)
        pages = await asyncio.gather(*(self._get(http, slug, day, sem) for slug, day in jobs))
        for (slug, day), payload in zip(jobs, pages):
            attempted += 1
            if payload is None:
                failed += 1
                continue
            self._fetched[(slug, day)] = mono
            fixtures = parse_scoreboard(payload, slug, self.leagues[slug])
            if any(_is_hot(f, now) for f in fixtures):
                self._hot.add((slug, day))
            else:
                self._hot.discard((slug, day))
            for f in fixtures:
                found[f.external_id] = f

        if attempted and failed == attempted:
            raise RuntimeError(f"ESPN unreachable ({failed} requests failed)")
        log.info("ESPN: %s requests (%s failed), %s fixtures, %s live pages", attempted, failed, len(found), len(self._hot))
        return list(found.values())
