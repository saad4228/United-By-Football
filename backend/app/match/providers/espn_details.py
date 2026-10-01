"""Match details (line-ups, key events, team stats, recent form) and league tables from
ESPN's public site API, the same undocumented feed the fixtures come from.

Fetched on demand when a match or competition page is opened, and cached with a TTL
that depends on how live the data is. Parsing is kept in pure functions so it can be
tested against recorded payloads.
"""

import logging
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.match.providers.espn import LEAGUES, USER_AGENT, _hex, _secure

log = logging.getLogger(__name__)
SITE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer"
EVENT_ID = re.compile(r"^\d{1,12}$")
LEAGUE_SLUG = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+){0,3}$")

# Team stats shown on the match page, in display order: (ESPN name, our key, unit).
STATS = [
    ("possessionPct", "possession", "%"),
    ("totalShots", "shots", ""),
    ("shotsOnTarget", "shots_on_target", ""),
    ("wonCorners", "corners", ""),
    ("totalPasses", "passes", ""),
    ("passPct", "pass_accuracy", "%"),
    ("foulsCommitted", "fouls", ""),
    ("offsides", "offsides", ""),
    ("saves", "saves", ""),
    ("yellowCards", "yellow_cards", ""),
    ("redCards", "red_cards", ""),
]
SHOOTOUT_PERIOD = 5


# ---------------------------------------------------------------- line-ups

def _depth(position: str | None) -> float:
    """How far up the pitch a position plays: 0 goalkeeper ... 5 centre-forward."""
    pos = (position or "").upper()
    if pos in ("G", "GK"):
        return 0
    base = pos.split("-")[0]
    return {
        "LB": 1, "RB": 1, "CD": 1, "CB": 1, "D": 1, "SW": 1,
        "LWB": 1.5, "RWB": 1.5, "WB": 1.5,
        "DM": 2, "CDM": 2,
        "CM": 3, "LM": 3, "RM": 3, "M": 3,
        "AM": 4, "CAM": 4, "LW": 4, "RW": 4, "SS": 4.5,
        "F": 5, "CF": 5, "ST": 5, "LF": 5, "RF": 5,
    }.get(base, 3)


def _lateral(position: str | None) -> int:
    """-2 (left touchline) ... 2 (right touchline), from the team's own point of view."""
    pos = (position or "").upper()
    if pos.endswith("-L"):
        return -1
    if pos.endswith("-R"):
        return 1
    base = pos.split("-")[0]
    if base in ("LB", "LWB", "LM", "LW", "LF"):
        return -2
    if base in ("RB", "RWB", "RM", "RW", "RF"):
        return 2
    return 0


def formation_lines(formation: str | None, starters: list[dict]) -> list[list[dict]] | None:
    """Group starters into lines (goalkeeper first) using the formation string and each
    player's position. Returns None if they don't add up, so the caller shows a plain list."""
    if not formation or len(starters) != 11:
        return None
    try:
        counts = [int(n) for n in formation.split("-")]
    except ValueError:
        return None
    keepers = [p for p in starters if _depth(p.get("position")) == 0]
    outfield = [p for p in starters if _depth(p.get("position")) != 0]
    if len(keepers) != 1 or sum(counts) != len(outfield) or any(n <= 0 for n in counts):
        return None
    outfield.sort(key=lambda p: (_depth(p.get("position")), p.get("_place", 99)))
    lines, start = [keepers], 0
    for n in counts:
        line = outfield[start:start + n]
        line.sort(key=lambda p: (_lateral(p.get("position")), p.get("_place", 99)))
        lines.append(line)
        start += n
    return lines


def _stat_value(stats: list[dict], name: str) -> float:
    for s in stats or []:
        if s.get("name") == name:
            try:
                return float(s.get("value") or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def _player(entry: dict) -> dict:
    athlete = entry.get("athlete") or {}
    stats = entry.get("stats") or []
    try:
        place = int(entry.get("formationPlace") or 99)
    except ValueError:
        place = 99
    position = (entry.get("position") or {}).get("abbreviation")
    return {
        "name": athlete.get("displayName") or athlete.get("fullName") or "Unknown",
        "short_name": athlete.get("shortName"),
        "number": str(entry["jersey"]) if entry.get("jersey") not in (None, "") else None,
        "position": None if position == "SUB" else position,
        "subbed_in": bool(entry.get("subbedIn")),
        "subbed_out": bool(entry.get("subbedOut")),
        "goals": int(_stat_value(stats, "totalGoals")),
        "yellow": _stat_value(stats, "yellowCards") > 0,
        "red": _stat_value(stats, "redCards") > 0,
        "_place": place,
    }


def _clean(player: dict) -> dict:
    return {k: v for k, v in player.items() if not k.startswith("_")}


def parse_lineup(roster: dict) -> dict | None:
    entries = roster.get("roster") or []
    if not entries:
        return None
    players = [_player(e) for e in entries]
    starters = [p for p, e in zip(players, entries) if e.get("starter")]
    subs = [p for p, e in zip(players, entries) if not e.get("starter")]
    formation = roster.get("formation") or None
    lines = formation_lines(formation, starters)
    starters.sort(key=lambda p: p["_place"])
    return {
        "formation": formation,
        "lines": [[_clean(p) for p in line] for line in lines] if lines else None,
        "starters": [_clean(p) for p in starters],
        # Players who came on first, then the unused bench.
        "subs": [_clean(p) for p in sorted(subs, key=lambda p: not p["subbed_in"])],
    }


# ---------------------------------------------------------------- events

def _event_kind(event: dict) -> str | None:
    kind = ((event.get("type") or {}).get("type") or "").lower()
    period = (event.get("period") or {}).get("number") or 0
    if period >= SHOOTOUT_PERIOD and "period" not in kind:
        return None  # shootout kicks aren't goals
    if kind == "own-goal":
        return "own_goal"
    if event.get("scoringPlay") or kind.startswith("goal"):
        return "penalty_goal" if "penalty" in kind else "goal"
    if "penalty" in kind and ("miss" in kind or "saved" in kind):
        return "missed_penalty"
    if kind in ("yellow-red-card", "second-yellow-card") or kind.startswith("red-card"):
        return "red"
    if kind.startswith("yellow-card"):
        return "yellow"
    if kind == "substitution":
        return "sub"
    if kind in ("halftime", "end-regular-time", "end-extra-time", "start-extra-time", "start-shootout", "penalty-shootout"):
        return "period"
    return None


PERIOD_LABELS = {
    "halftime": "halftime",
    "end-regular-time": "fulltime",
    "start-extra-time": "extra_time",
    "end-extra-time": "end_extra_time",
    "start-shootout": "penalties",
    "penalty-shootout": "penalties",
}


def parse_events(key_events: list[dict], sides: dict[str, str]) -> list[dict]:
    """Goals, cards, substitutions and period markers, in match order. `sides` maps ESPN
    team id -> "home"/"away". Own goals are credited to the team that benefits, as ESPN does."""
    out: list[dict] = []
    goals = {"home": 0, "away": 0}
    for event in key_events or []:
        kind = _event_kind(event)
        if kind is None:
            continue
        side = sides.get(str((event.get("team") or {}).get("id")))
        names = [((p.get("athlete") or {}).get("displayName")) for p in event.get("participants") or []]
        minute = (event.get("clock") or {}).get("displayValue") or None
        item: dict[str, Any] = {"kind": kind, "minute": minute, "side": side}
        if kind == "period":
            label = PERIOD_LABELS[((event.get("type") or {}).get("type") or "").lower()]
            item.update(side=None, label=label, score=f"{goals['home']}-{goals['away']}")
        elif kind in ("goal", "own_goal", "penalty_goal"):
            if side:
                goals[side] += 1
            item.update(player=names[0] if names else None,
                        assist=names[1] if kind == "goal" and len(names) > 1 else None,
                        score=f"{goals['home']}-{goals['away']}")
        elif kind == "sub":
            item.update(player=names[0] if names else None, assist=names[1] if len(names) > 1 else None)
        else:
            item.update(player=names[0] if names else None)
        out.append(item)
    # Drop a trailing marker that only repeats the previous one (e.g. HT reported twice).
    return [e for i, e in enumerate(out) if not (e["kind"] == "period" and i and out[i - 1] == e)]


# ---------------------------------------------------------------- stats and form

def parse_stats(boxscore: dict, sides: dict[str, str]) -> list[dict]:
    teams = {}
    for i, team in enumerate((boxscore or {}).get("teams") or []):
        side = team.get("homeAway") or sides.get(str((team.get("team") or {}).get("id"))) or ("home", "away")[min(i, 1)]
        teams[side] = {s.get("name"): s.get("displayValue") for s in team.get("statistics") or []}
    if "home" not in teams or "away" not in teams:
        return []
    out = []
    for name, key, unit in STATS:
        raw = (teams["home"].get(name), teams["away"].get(name))
        if raw[0] in (None, "") or raw[1] in (None, ""):
            continue
        try:
            if key == "pass_accuracy":
                # ESPN rounds this to one decimal (0.9); work it out from the pass counts instead.
                home, away = (round(100 * float(teams[s]["accuratePasses"]) / float(teams[s]["totalPasses"]))
                              for s in ("home", "away"))
            else:
                home, away = float(raw[0]), float(raw[1])
        except (ValueError, KeyError, TypeError, ZeroDivisionError):
            continue
        out.append({"key": key, "home": home, "away": away, "unit": unit})
    # Before kick-off ESPN sends a block of zeros; that's not worth showing.
    return out if any(s["home"] or s["away"] for s in out) else []


def _date(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_form(last_five: list[dict], sides: dict[str, str]) -> dict[str, list[dict]] | None:
    form: dict[str, list[dict]] = {}
    for block in last_five or []:
        side = sides.get(str((block.get("team") or {}).get("id")))
        if not side:
            continue
        games = []
        for e in block.get("events") or []:
            result = e.get("gameResult")
            if result not in ("W", "D", "L"):
                continue
            games.append({
                "result": result,
                "score": e.get("score"),
                "opponent": (e.get("opponent") or {}).get("displayName") or "",
                "home": e.get("atVs") != "@",
                "date": _date(e.get("gameDate")),
            })
        # Oldest first, so the newest result sits on the right.
        form[side] = sorted(games, key=lambda g: g["date"] or datetime.min)[-5:]
    return form or None


def parse_summary(payload: dict) -> dict:
    competitors = ((payload.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or []
    sides = {str((c.get("team") or {}).get("id") or c.get("id")): c.get("homeAway") for c in competitors
             if c.get("homeAway") in ("home", "away")}
    lineups = {}
    for roster in payload.get("rosters") or []:
        side = roster.get("homeAway") or sides.get(str((roster.get("team") or {}).get("id")))
        lineup = parse_lineup(roster)
        if side in ("home", "away") and lineup:
            lineups[side] = lineup
    attendance = ((payload.get("gameInfo") or {}).get("attendance")) or None
    return {
        "available": True,
        "lineups": lineups if len(lineups) == 2 else None,
        "events": parse_events(payload.get("keyEvents") or [], sides),
        "stats": parse_stats(payload.get("boxscore") or {}, sides),
        "form": parse_form(payload.get("lastFiveGames") or [], sides),
        "attendance": int(attendance) if isinstance(attendance, (int, float)) and attendance > 0 else None,
    }


# ---------------------------------------------------------------- standings

def parse_standings(payload: dict, women: bool = False) -> dict:
    season = (payload.get("season") or {}).get("displayName") if isinstance(payload.get("season"), dict) else None
    groups, legend, seen = [], [], set()
    for child in payload.get("children") or []:
        rows = []
        for entry in (child.get("standings") or {}).get("entries") or []:
            team = entry.get("team") or {}
            stats = {s.get("name"): s.get("value") for s in entry.get("stats") or []}

            def num(name: str) -> int:
                try:
                    return int(float(stats.get(name) or 0))
                except (TypeError, ValueError):
                    return 0

            note = entry.get("note") or None
            note_out = None
            if note and note.get("description"):
                note_out = {"label": str(note["description"])[:60], "color": _hex(note.get("color"))}
                if (note_out["label"], note_out["color"]) not in seen:
                    seen.add((note_out["label"], note_out["color"]))
                    legend.append(note_out)
            logos = team.get("logos") or []
            team_id = team.get("id")
            rows.append({
                "rank": num("rank"),
                "name": team.get("displayName") or team.get("name") or "Unknown",
                "short_name": team.get("shortDisplayName") or team.get("abbreviation"),
                "logo_url": _secure(logos[0].get("href")) if logos else None,
                "external_id": f"{'w' if women else ''}{team_id}" if team_id else None,
                "played": num("gamesPlayed"),
                "won": num("wins"),
                "drawn": num("ties"),
                "lost": num("losses"),
                "goals_for": num("pointsFor"),
                "goals_against": num("pointsAgainst"),
                "goal_difference": num("pointDifferential"),
                "points": num("points"),
                "note": note_out,
            })
        if not rows:
            continue
        rows.sort(key=lambda r: (r["rank"] or 999, -r["points"], -r["goal_difference"]))
        name = child.get("name")
        groups.append({"name": name, "rows": rows})
    if len(groups) == 1 and (groups[0]["name"] == season or not groups[0]["name"]):
        groups[0]["name"] = None
    return {"available": bool(groups), "season": season, "groups": groups, "legend": legend}


# ---------------------------------------------------------------- service

def details_ttl(status: str, kickoff: datetime, now: datetime) -> int:
    if status in ("live", "halftime"):
        return 30
    if status == "scheduled":
        # Line-ups drop about an hour before kick-off.
        return 120 if kickoff - now < timedelta(hours=3) else 1800
    if status == "finished":
        return 300 if now - kickoff < timedelta(hours=6) else 6 * 3600
    return 1800


class ESPNDetails:
    """On-demand ESPN lookups with a small TTL cache (also caches failures briefly)."""

    MAX_ENTRIES = 512
    FAILURE_TTL = 60

    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self._cache: OrderedDict[str, tuple[float, dict | None]] = OrderedDict()

    async def _get(self, url: str, params: dict, ttl: int) -> dict | None:
        key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        hit = self._cache.get(key)
        mono = time.monotonic()
        if hit and hit[0] > mono:
            self._cache.move_to_end(key)
            return hit[1]
        try:
            response = await self.http.get(url, params=params, timeout=10, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("unexpected payload")
            expires = mono + ttl
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("ESPN details %s failed: %s", url, exc)
            data, expires = None, mono + self.FAILURE_TTL
            if hit:  # serve the stale copy rather than nothing
                data = hit[1]
        self._cache[key] = (expires, data)
        self._cache.move_to_end(key)
        while len(self._cache) > self.MAX_ENTRIES:
            self._cache.popitem(last=False)
        return data

    async def match(self, event_id: str, status: str, kickoff: datetime, now: datetime) -> dict | None:
        if not EVENT_ID.match(event_id):
            return None
        payload = await self._get(f"{SITE_URL}/all/summary", {"event": event_id}, details_ttl(status, kickoff, now))
        return parse_summary(payload) if payload else None

    async def standings(self, league: str) -> dict | None:
        if not LEAGUE_SLUG.match(league):
            return None
        payload = await self._get(f"{STANDINGS_URL}/{league}/standings", {}, 300)
        if not payload:
            return None
        return parse_standings(payload, women=LEAGUES[league].women if league in LEAGUES else False)
