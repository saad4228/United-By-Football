"""Team banners and club facts.

* Facts (founded, stadium, capacity, website) come from TheSportsDB's free API.
* The banner is a freely licensed photograph of the team's home stadium from Wikimedia
  Commons. Author, licence and file page are stored with it so every banner can carry the
  credit its licence requires.

Lookups are rate-limited per service, run once per team, and are refreshed monthly
(failed lookups are retried after a few hours).
"""

import asyncio
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy import exists, func, or_, select

from app import __version__
from app.config import Settings
from app.database.models import Match, Team, TeamMedia
from app.database.session import Database
from app.match.normalize import name_similarity, normalize_name
from app.utils.text import sanitize_text
from app.utils.time import utcnow

log = logging.getLogger(__name__)

SPORTSDB_URL = "https://www.thesportsdb.com/api/v1/json/{key}/searchteams.php"
WIKI_API = "https://en.wikipedia.org/w/api.php"
FRESH_FOR = timedelta(days=30)
RETRY_PARTIAL_AFTER = timedelta(days=7)  # stadium known but no usable photo yet
RETRY_ERRORS_AFTER = timedelta(hours=6)
VENUE_WORDS = ("stadium", "arena", "ground", "venue", "stadion", "estadio", "estádio", "stade", "field", "park", "stadio")
GENERIC_TOKENS = {"stadium", "stadion", "estadio", "estadio", "stade", "stadio", "arena", "park", "ground", "field", "the",
                  "de", "do", "da", "del", "di", "of", "sports", "football", "municipal", "national", "nacional"}
FREE_LICENSES = ("cc0", "cc by", "cc-by", "public domain", "pd", "attribution")
IMAGE_HOSTS = ("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")
SECOND_TEAM = re.compile(r"\b(reserves?|ii|b|u\d{2}|youth|academy)\b", re.IGNORECASE)
SKIP_IMAGE = re.compile(r"logo|crest|badge|map|flag|kit|icon|locator|seating|plan|diagram", re.IGNORECASE)
_COUNTRY_ALIASES = {"usa": "unitedstates", "us": "unitedstates", "ksa": "saudiarabia"}
# Feeds disagree on some national-team names; try the other common form too.
NATIONAL_NAME_VARIANTS = {
    "czechia": "Czech Republic", "czech republic": "Czechia", "turkiye": "Turkey", "turkey": "Türkiye",
    "united states": "USA", "usa": "United States", "south korea": "Korea Republic", "korea republic": "South Korea",
    "ivory coast": "Côte d'Ivoire", "cote divoire": "Ivory Coast", "iran": "IR Iran", "ir iran": "Iran",
    "china pr": "China", "china": "China PR", "republic of ireland": "Ireland", "ireland": "Republic of Ireland",
    "north macedonia": "Macedonia", "cape verde": "Cape Verde Islands", "dr congo": "Congo DR", "congo dr": "DR Congo",
}


class RateLimiter:
    """At most one request per `interval` seconds, across all callers."""

    def __init__(self, interval: float):
        self.interval = interval
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if self._next > now:
                await asyncio.sleep(self._next - now)
            self._next = max(now, self._next) + self.interval


@dataclass
class ClubFacts:
    sportsdb_id: str | None
    country: str | None
    founded: int | None
    stadium: str | None
    capacity: int | None
    website: str | None


@dataclass
class Photo:
    url: str
    page: str | None
    subject: str
    author: str | None
    license: str
    license_url: str | None


def _country_key(value: str | None) -> str | None:
    if not value:
        return None
    key = re.sub(r"[^a-z]", "", normalize_name(value))
    return _COUNTRY_ALIASES.get(key, key)


def _int(value: object) -> int | None:
    try:
        number = int(str(value).strip())
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def _website(value: object) -> str | None:
    text = str(value or "").strip()
    if not text or " " in text or "." not in text:
        return None
    if not text.startswith(("http://", "https://")):
        text = "https://" + text.lstrip("/")
    return text[:255]


def is_women(name: str) -> bool:
    return bool(re.search(r"\bwomen\b|\bwfc\b|\bladies\b|\bfemenin", name, re.IGNORECASE))


def strip_women(name: str) -> str:
    return re.sub(r"\s+(women|wfc|ladies)$", "", name, flags=re.IGNORECASE).strip()


def significant_tokens(value: str) -> set[str]:
    return {t for t in normalize_name(value).split() if t not in GENERIC_TOKENS and len(t) > 2}


def is_venue_page(page: dict) -> bool:
    text = f"{page.get('title', '')} {page.get('description', '')}".lower()
    return bool(page.get("pageimage")) and any(word in text for word in VENUE_WORDS)


def venue_score(page: dict, stadium: str, team_name: str | None = None) -> int:
    """How many of the stadium's (and team's) distinctive words the page mentions. The intro
    sentence counts too: stadium articles nearly always open with "...home of <club>"."""
    wanted = significant_tokens(stadium) | (significant_tokens(strip_women(team_name)) if team_name else set())
    found = significant_tokens(f"{page.get('title', '')} {page.get('description', '')} {page.get('extract', '')}")
    return len(wanted & found)


def looks_like_venue(page: dict, stadium: str, team_name: str | None = None) -> bool:
    if not is_venue_page(page):
        return False
    # Must actually be *this* venue, not another stadium the search happened to return.
    if page.get("redirected") or not significant_tokens(stadium):
        return True
    return venue_score(page, stadium, team_name) >= 1


def pick_club(candidates: list[dict], team_name: str, country: str | None, women: bool) -> dict | None:
    wanted = normalize_name(strip_women(team_name))
    country_key = _country_key(country)
    best, best_score = None, 0.0
    for c in candidates:
        if c.get("strSport") != "Soccer":
            continue
        if (str(c.get("strGender") or "Male").lower() == "female") != women:
            continue
        if country_key and c.get("strCountry") and _country_key(c["strCountry"]) != country_key:
            continue
        if SECOND_TEAM.search(c.get("strTeam") or "") and not SECOND_TEAM.search(team_name):
            continue  # "Mumbai City FC Reserves" is not Mumbai City FC
        forms = {normalize_name(c.get("strTeam") or "")}
        forms |= {normalize_name(a) for a in str(c.get("strTeamAlternate") or "").split(",") if a.strip()}
        score = name_similarity(wanted, {f for f in forms if f})
        if score > best_score:
            best, best_score = c, score
    return best if best_score >= 0.86 else None


class MediaService:
    def __init__(self, db: Database, settings: Settings, http: httpx.AsyncClient):
        self.db = db
        self.settings = settings
        self.http = http
        self.headers = {
            # Wikimedia's API policy: name/version (contact) library/version.
            "User-Agent": f"UnitedByFootball/{__version__} (+{settings.contact_url}) python-httpx/{httpx.__version__}"
        }
        self.sportsdb_limit = RateLimiter(2.2)  # free tier allows ~30 requests a minute
        self.wiki_limit = RateLimiter(0.35)
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._inflight: dict[int, asyncio.Task] = {}

    async def _get(self, url: str, params: dict, limiter: RateLimiter) -> dict | None:
        await limiter.wait()
        try:
            response = await self.http.get(url, params=params, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.info("media lookup failed (%s): %s", url.split("/")[2], exc)
            raise

    # ---- TheSportsDB -----------------------------------------------------------------
    async def find_club(self, team: Team) -> ClubFacts | None:
        women = is_women(team.name)
        queries = [strip_women(team.name)]
        if team.short_name and strip_women(team.short_name) not in queries:
            queries.append(strip_women(team.short_name))
        variant = NATIONAL_NAME_VARIANTS.get(normalize_name(strip_women(team.name)))
        if variant and variant not in queries:
            queries.append(variant)
        url = SPORTSDB_URL.format(key=self.settings.sportsdb_key)
        for query in queries:
            data = await self._get(url, {"t": query}, self.sportsdb_limit) or {}
            club = pick_club(data.get("teams") or [], query, team.country, women)
            if club:
                return ClubFacts(
                    sportsdb_id=str(club.get("idTeam") or "") or None,
                    country=sanitize_text(club.get("strCountry"), 80),
                    founded=_int(club.get("intFormedYear")),
                    stadium=sanitize_text(club.get("strStadium"), 160),
                    capacity=_int(club.get("intStadiumCapacity")),
                    website=_website(club.get("strWebsite")),
                )
        return None

    # ---- Wikimedia ---------------------------------------------------------------------
    async def _wiki(self, **params) -> dict:
        return await self._get(WIKI_API, {**params, "format": "json", "formatversion": 2}, self.wiki_limit) or {}

    async def find_photo(self, stadium: str, team_name: str | None = None) -> Photo | None:
        common = {"prop": "pageimages|description|extracts", "piprop": "name", "pilicense": "free", "redirects": 1,
                  "exintro": 1, "explaintext": 1, "exsentences": 2, "exlimit": 10}
        data = await self._wiki(action="query", titles=stadium, **common)
        redirected = bool(data.get("query", {}).get("redirects"))
        exact = [{**p, "redirected": redirected} for p in data.get("query", {}).get("pages", []) if not p.get("missing")]
        candidates = [p for p in exact if looks_like_venue(p, stadium)]
        if not candidates:
            # Sponsor names often have no article ("Allianz Stadium Turin", "Chobani Stadyumu"):
            # search with the team's name and keep the venue that mentions the most of the
            # stadium's and team's words.
            query = f"{stadium} {strip_women(team_name)}" if team_name else f"{stadium} stadium"
            data = await self._wiki(action="query", generator="search", gsrsearch=query, gsrlimit=6, **common)
            pages = [p for p in data.get("query", {}).get("pages", []) if looks_like_venue(p, stadium, team_name)]
            candidates = sorted(pages, key=lambda p: (-venue_score(p, stadium, team_name), p.get("index", 99)))[:2]
        return await self._photo_from_pages(candidates)

    async def find_home_ground_photo(self, team_name: str) -> Photo | None:
        """Last resort: "<team> stadium", accepted only if the article names the club."""
        common = {"prop": "pageimages|description|extracts", "piprop": "name", "pilicense": "free", "redirects": 1,
                  "exintro": 1, "explaintext": 1, "exsentences": 2, "exlimit": 10}
        name = strip_women(team_name)
        data = await self._wiki(action="query", generator="search", gsrsearch=f"{name} stadium home ground",
                                gsrlimit=6, **common)
        club = significant_tokens(name)
        pages = [
            p for p in sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
            if is_venue_page(p) and club and club <= significant_tokens(f"{p.get('title', '')} {p.get('extract', '')}")
        ]
        return await self._photo_from_pages(pages[:2])

    async def _photo_from_pages(self, candidates: list[dict]) -> Photo | None:
        for page in candidates:
            photo = await self._image(page["pageimage"], page["title"])
            if photo:
                return photo
            # Lead image unusable (too small, portrait): try the article's other photos.
            photo = await self._best_article_photo(page["title"])
            if photo:
                return photo
        return None

    async def _best_article_photo(self, title: str) -> Photo | None:
        data = await self._wiki(action="query", titles=title, prop="images", imlimit=40, redirects=1)
        pages = data.get("query", {}).get("pages", [])
        names = [img["title"] for img in (pages[0].get("images") or [])] if pages else []
        photos = [n for n in names if n.lower().endswith((".jpg", ".jpeg")) and not SKIP_IMAGE.search(n)][:20]
        if not photos:
            return None
        data = await self._wiki(action="query", titles="|".join(photos), prop="imageinfo",
                                iiprop="url|size|extmetadata", iiurlwidth=1920)
        best: tuple[int, Photo] | None = None
        for page in data.get("query", {}).get("pages", []):
            info = (page.get("imageinfo") or [{}])[0]
            photo = self._photo_from_info(info, title)
            if photo and (best is None or info.get("width", 0) > best[0]):
                best = (info.get("width", 0), photo)
        return best[1] if best else None

    async def _image(self, file_name: str, subject: str) -> Photo | None:
        data = await self._wiki(action="query", titles=f"File:{file_name}", prop="imageinfo",
                                iiprop="url|size|extmetadata", iiurlwidth=1920)
        pages = data.get("query", {}).get("pages", [])
        info = (pages[0].get("imageinfo") or [{}])[0] if pages else {}
        return self._photo_from_info(info, subject)

    @staticmethod
    def _photo_from_info(info: dict, subject: str) -> Photo | None:
        width, height = info.get("width") or 0, info.get("height") or 1
        if width < 1200 or not 1.25 <= width / height <= 3.2:
            return None  # banners need a wide, sharp image
        meta = info.get("extmetadata") or {}
        license_name = sanitize_text((meta.get("LicenseShortName") or {}).get("value"), 60) or ""
        if not license_name.lower().startswith(FREE_LICENSES):
            return None
        url = info.get("thumburl") or info.get("url")
        if not url or not url.startswith(IMAGE_HOSTS):
            return None
        url = url.split("?", 1)[0]  # drop Wikimedia's tracking parameters
        return Photo(
            url=url,
            page=info.get("descriptionurl"),
            subject=sanitize_text(subject, 200) or subject,
            author=sanitize_text((meta.get("Artist") or {}).get("value"), 200),
            license=license_name,
            license_url=(meta.get("LicenseUrl") or {}).get("value"),
        )

    # ---- orchestration -------------------------------------------------------------------
    @staticmethod
    def is_fresh(media: TeamMedia | None) -> bool:
        if media is None:
            return False
        if media.locked:
            return True  # curated by hand: never looked up again
        age = utcnow() - media.checked_at
        limit = {"error": RETRY_ERRORS_AFTER, "partial": RETRY_PARTIAL_AFTER}.get(media.status, FRESH_FOR)
        return age < limit

    async def _home_venue(self, team_id: int) -> str | None:
        async with self.db.sessions() as session:
            row = await session.execute(
                select(Match.venue, func.count(Match.id).label("n"))
                .where(Match.home_team_id == team_id, Match.venue.is_not(None))
                .group_by(Match.venue)
                .order_by(func.count(Match.id).desc())
                .limit(1)
            )
            hit = row.first()
            return hit[0] if hit else None

    async def enrich(self, team_id: int, force: bool = False) -> TeamMedia | None:
        async with self._locks[team_id]:
            async with self.db.sessions() as session:
                team = await session.get(Team, team_id)
                media = await session.get(TeamMedia, team_id)
                if team is None:
                    return None
                if media and (media.locked or (not force and self.is_fresh(media))):
                    return media
            facts: ClubFacts | None = None
            photo: Photo | None = None
            stadium: str | None = None
            try:
                facts = await self.find_club(team)
                venue = await self._home_venue(team_id)
                stadium = (facts.stadium if facts else None) or venue
                # Try every name we know for the ground, then the club's own home-ground search.
                for name in dict.fromkeys(n for n in (stadium, venue) if n):
                    photo = await self.find_photo(name, team.name)
                    if photo:
                        break
                if photo is None:
                    photo = await self.find_home_ground_photo(team.name)
                status = "ok" if photo else "partial" if facts or stadium else "none"
            except (httpx.HTTPError, ValueError):
                status = "error"

            async with self.db.sessions() as session:
                media = await session.get(TeamMedia, team_id)
                if media is None:
                    media = TeamMedia(team_id=team_id, status=status)
                    session.add(media)
                media.checked_at = utcnow()
                if facts and facts.country:
                    # Teams first seen in a European cup arrive without a country.
                    stored = await session.get(Team, team_id)
                    if stored and not stored.country:
                        stored.country = facts.country
                if status == "error" and media.status in ("ok", "partial"):
                    pass  # keep what we already had; retry later
                else:
                    media.status = status
                    media.sportsdb_id = facts.sportsdb_id if facts else None
                    media.founded = facts.founded if facts else None
                    media.capacity = facts.capacity if facts else None
                    media.website = facts.website if facts else None
                    media.stadium = stadium
                    for field in ("url", "page", "subject", "author", "license", "license_url"):
                        setattr(media, f"photo_{field}", getattr(photo, field) if photo else None)
                await session.commit()
                return media

    async def get_or_enrich(self, team_id: int, timeout: float = 8.0) -> TeamMedia | None:
        """Return stored media; if there is none yet, look it up (in the background if slow)."""
        async with self.db.sessions() as session:
            media = await session.get(TeamMedia, team_id)
        if media and self.is_fresh(media):
            return media
        task = self._inflight.get(team_id)
        if task is None or task.done():
            task = asyncio.create_task(self.enrich(team_id))
            self._inflight[team_id] = task
            task.add_done_callback(lambda _t, tid=team_id: self._inflight.pop(tid, None))
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout)
        except asyncio.TimeoutError:
            return media  # stale or None; the lookup keeps running

    async def next_team(self) -> int | None:
        """Teams with matches soon and the biggest following first."""
        now = utcnow()
        soon = exists().where(
            or_(Match.home_team_id == Team.id, Match.away_team_id == Team.id),
            Match.kickoff_time.between(now - timedelta(days=1), now + timedelta(days=14)),
        )
        stale = or_(TeamMedia.team_id.is_(None), TeamMedia.checked_at < now - FRESH_FOR,
                    (TeamMedia.status == "partial") & (TeamMedia.checked_at < now - RETRY_PARTIAL_AFTER),
                    (TeamMedia.status == "error") & (TeamMedia.checked_at < now - RETRY_ERRORS_AFTER))
        async with self.db.sessions() as session:
            return await session.scalar(
                select(Team.id)
                .outerjoin(TeamMedia, TeamMedia.team_id == Team.id)
                .where(stale, TeamMedia.locked.is_not(True))
                .order_by(soon.desc(), Team.popularity.desc(), Team.id)
                .limit(1)
            )

    async def run_forever(self, pause: float = 4.0) -> None:
        await asyncio.sleep(5)
        while True:
            try:
                team_id = await self.next_team()
                if team_id is None:
                    await asyncio.sleep(600)
                    continue
                await self.enrich(team_id)
            except Exception:
                log.exception("media loop error")
            await asyncio.sleep(pause)
