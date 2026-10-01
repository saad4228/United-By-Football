"""Simulated third-party sources for demo mode, served under /mock-sources.

Two fake "sites" list today's demo fixtures using deliberately inconsistent naming
(the web listing uses nicknames, the API uses three-letter codes) so the
normalizer has real work to do. Their links lead through redirect layers to
destination pages whose behaviour is deterministic per link: stable, redirect
chains, flaky, slow, rate-limited or dead. No external traffic is involved.
"""

import asyncio
import hashlib
import html
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.config import get_settings
from app.database.seed_data import COMPETITIONS, TEAMS
from app.demo.schedule import matches_between

router = APIRouter(prefix="/mock-sources", include_in_schema=False)

_TEAMS = {t[0]: t for t in TEAMS}
_COMP_SHORT = {"PL": "EPL", "PD": "LaLiga", "BL1": "Bundesliga", "SA": "Serie A", "FL1": "Ligue 1",
               "CL": "UCL", "EL": "UEL", "MLS": "MLS"}
_COMP_NAMES = {c[1]: c[2] for c in COMPETITIONS}
_LANGS = ["English", "English", "Spanish", "English", "French", "German", "Arabic", "Portuguese"]


def _h(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def _nickname(slug: str, salt: int) -> str:
    _, name, short, _, _, _, _, _, _, aliases = _TEAMS[slug]
    options = [short, *aliases[:2], name]
    return options[salt % len(options)]


def _window(now: datetime):
    return matches_between(now - timedelta(hours=2, minutes=30), now + timedelta(hours=8))


def profile_for(token: str) -> str:
    bucket = _h("profile", token) % 100
    if bucket < 42:
        return "stable"
    if bucket < 62:
        return "chain"
    if bucket < 76:
        return "flaky"
    if bucket < 86:
        return "slow"
    if bucket < 92:
        return "ratelimited"
    return "dead"


def _base() -> str:
    return get_settings().demo_source_base_url


@router.get("/listing", response_class=HTMLResponse)
async def web_listing() -> HTMLResponse:
    """A cluttered "stream guide" page — the kind the web connector has to parse."""
    now = datetime.now(timezone.utc)
    rows = []
    for m in _window(now):
        if _h("web-skip", m.slot) % 5 == 0:
            continue  # sources never list everything
        salt = _h("web-name", m.slot)
        links = []
        for i in range(1 + _h("web-n", m.slot) % 3):
            token = f"w{m.slot}x{i}"
            lang = _LANGS[_h("lang", token) % len(_LANGS)]
            links.append(
                f'<a class="stream-link" href="{_base()}/go/{token}" data-lang="{lang}" data-quality="HD">'
                f"Channel {i + 1}</a>"
            )
        title = f"{_nickname(m.home, salt)} v {_nickname(m.away, salt >> 4)}"
        rows.append(
            f'<div class="event-row"><span class="league">{_COMP_SHORT[m.competition]}</span>'
            f'<time datetime="{m.kickoff.isoformat()}">{m.kickoff:%H:%M}</time>'
            f'<h3 class="event-title">{html.escape(title)}</h3>'
            f'<div class="ad-slot">Sponsored — Bet now!</div>{"".join(links)}</div>'
        )
    # An event that does not exist in our fixture list: must be ignored, not invented.
    rows.append(
        '<div class="event-row"><span class="league">Friendly</span>'
        f'<time datetime="{now.isoformat()}">{now:%H:%M}</time>'
        '<h3 class="event-title">Northfield Rovers v Eastbrook Athletic</h3>'
        f'<a class="stream-link" href="{_base()}/go/unknown-1">Channel 1</a></div>'
    )
    page = (
        "<!doctype html><html><head><title>Demo Stream Guide</title></head><body>"
        '<nav>Home | Football | Basketball | Tennis</nav><div class="ad-banner">Advert</div>'
        f'<main id="schedule">{"".join(rows)}</main></body></html>'
    )
    return HTMLResponse(page)


@router.get("/api/events")
async def api_events() -> JSONResponse:
    """A JSON feed that uses three-letter codes and slightly-off kickoff times."""
    now = datetime.now(timezone.utc)
    events = []
    for m in _window(now):
        if _h("api-skip", m.slot) % 10 < 3:
            continue
        jitter = timedelta(minutes=(_h("jitter", m.slot) % 11) - 5)
        streams = []
        for i in range(1 + _h("api-n", m.slot) % 2):
            token = f"a{m.slot}x{i}"
            streams.append({
                "url": f"{_base()}/r/{token}",
                "name": f"Feed {chr(65 + i)}",
                "lang": _LANGS[_h("lang", token) % len(_LANGS)],
                "quality": "1080p" if i == 0 else "720p",
            })
        events.append({
            "id": f"evt-{m.slot}",
            "home": _TEAMS[m.home][3],
            "away": _TEAMS[m.away][3],
            "competition": _COMP_NAMES[m.competition],
            "start": (m.kickoff + jitter).isoformat(),
            "streams": streams,
        })
    return JSONResponse({"generated_at": now.isoformat(), "events": events})


@router.get("/go/{token}")
async def go(token: str) -> RedirectResponse:
    """Interstitial redirect layer in front of the web listing's links."""
    if profile_for(token) == "chain":
        return RedirectResponse(f"{_base()}/hop/{token}/1", status_code=302)
    return RedirectResponse(f"{_base()}/watch/{token}", status_code=302)


@router.get("/r/{token}")
async def api_redirect(token: str) -> RedirectResponse:
    return RedirectResponse(f"{_base()}/watch/{token}", status_code=307)


@router.get("/hop/{token}/{n}", response_model=None)
async def hop(token: str, n: int) -> RedirectResponse | HTMLResponse:
    if n >= 2:
        # Final hop is a meta-refresh page rather than an HTTP redirect.
        target = f"{_base()}/watch/{token}"
        return HTMLResponse(f'<html><head><meta http-equiv="refresh" content="0; url={target}"></head></html>')
    return RedirectResponse(f"{_base()}/hop/{token}/{n + 1}", status_code=301)


@router.get("/watch/{token}", response_class=HTMLResponse)
async def watch(token: str) -> HTMLResponse:
    profile = profile_for(token)
    minute_bucket = int(time.time() // 180)
    if token.startswith("unknown") or profile == "dead":
        return HTMLResponse("<h1>404</h1><p>Stream not found</p>", status_code=404)
    if profile == "flaky" and (_h("flaky", token, minute_bucket) % 3 == 0):
        return HTMLResponse("<h1>503</h1>", status_code=503)
    if profile == "ratelimited" and (_h("rl", token, minute_bucket) % 2 == 0):
        return HTMLResponse("Too many requests", status_code=429, headers={"Retry-After": "60"})
    if profile == "slow":
        await asyncio.sleep(0.6 + (_h("slow", token) % 10) / 10)
    return HTMLResponse(_destination_page(token))


def _destination_page(token: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo source destination</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#050505;color:#fff;
font:16px/1.5 system-ui,sans-serif}}main{{max-width:640px;padding:24px}}
.player{{aspect-ratio:16/9;border:1px solid #222;border-radius:10px;display:grid;place-items:center;
background:repeating-linear-gradient(135deg,#0a0a0a 0 14px,#0d0d0d 14px 28px);color:#888}}
h1{{font-size:20px;margin:20px 0 4px}}p{{color:#a3a3a3;margin:0}}code{{color:#d4d4d4}}
</style></head><body><main><div class="player">Demo destination — no video is hosted here</div>
<h1>This is where the third-party source would open</h1>
<p>United By Football resolved the redirect chain and sent you straight to the destination
(<code>{html.escape(token)}</code>). In production this is the source's own page.</p></main></body></html>"""
