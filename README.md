# United By Football

**Never miss the kickoff.** A football match discovery and source aggregation platform: one match → every available viewing source → one clean interface.

Designed and built by **Mohammad Saad**.

<sub>Profile picture: [Lionel Messi, Argentina v Egypt, 2026 FIFA World Cup](https://commons.wikimedia.org/wiki/File:Leo_Messi_Argentina_v_Egypt_7_July_2026-1.jpg) by Bryan Berlin, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), cropped. The cropped file `frontend/public/creator.webp` is shared under the same licence.</sub>

```
                 UNITED BY FOOTBALL
          ┌──────────────┴──────────────┐
     MATCH ENGINE                  SOURCE ENGINE
  fixtures · teams · scores    discovery · resolution · validation · health
          └──────────────┬──────────────┘
                  CLEAN EXPERIENCE
```

This repository is the PRD's **MVP v1**: a cinematic React frontend, a FastAPI backend with a modular connector architecture, match normalization and de-duplication, redirect resolution with SSRF protection, scheduled link health checks, and an admin dashboard.

---

## Quick start

### With Docker

```bash
docker compose up --build        # http://localhost:8000
```

One image builds the frontend with Node, then hands it to the Python backend, which serves the
site and the API together. The database lives in a named volume, so it survives restarts.

### Without Docker

Requirements: Python 3.11+ (tested on 3.14), Node 20+ (tested on 24).

```bash
# 1. Backend  (http://127.0.0.1:8000)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt      # macOS/Linux: .venv/bin/pip
cp .env.example .env                                    # optional; defaults work
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# 2. Frontend dev server  (http://localhost:5173, proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Or build the frontend once (`npm run build`) and the backend serves it at **http://127.0.0.1:8000** — one process, no Vite.

**Admin dashboard:** `/admin`. Set `UBF_ADMIN_TOKEN` in `.env`; if you don't, a random token is printed in the server log at startup.

**Tests:**

```bash
cd backend && .venv/Scripts/python -m pytest        # 118 backend tests, no network access needed
cd frontend && npm run build && npm run test:e2e    # 26 browser tests: desktop, Android and iPhone sizes
```

The browser tests (Playwright) start their own backend in demo mode on port 8010 with a throwaway
database, block every request that would leave the machine, and fail on any console or page error.
They also run axe-core against each page type, so a serious accessibility regression fails the build.
`PW_CHANNEL=msedge` (or `chrome`) uses an installed browser instead of Playwright's Chromium;
Playwright's own Chromium is the most reliable, since Edge throttles background tabs. GitHub Actions
(`.github/workflows/ci.yml`) runs both suites on every push and pull request.

### Match data (default: real)

Fixtures, live scores, results, crests and kit colours come from **ESPN's public scoreboard feed** (`app/match/providers/espn.py`). No API key needed. It covers about 35 competitions, set in `LEAGUES` or overridden with `UBF_ESPN_LEAGUES`:

- **Seeded big eight:** Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League, Europa League, MLS.
- **Internationals:** UEFA and Concacaf Nations League, friendlies.
- **Other competitions:** Conference League, Libertadores, Sudamericana, Primeira Liga, Eredivisie, Championship, Saudi Pro League, Brasileirão, Argentina, Liga MX, ISL, J.League, WSL, NWSL and more.

How the provider keeps requests low and data correct:

- **Match days only:** it reads each league's season calendar and requests only days with fixtures: the last round, today, and two weeks ahead. Cups publish rounds rather than days, so they're checked day by day for one week.
- **Live-aware caching:** each (league, day) page is cached. A day with a match in progress is re-fetched every 30 s, today otherwise every 5 min, future days hourly. The first sync is ~300 requests; after that a 30 s poll usually makes none.
- **Stable team identity:** teams are tracked by ESPN team id, so a renamed club stays the same team, and two different clubs with the same name in different countries never merge.
- **Women's teams kept separate:** women's sides are suffixed "Women", because ESPN names them exactly like the men's club.
- **Stale matches closed:** a match the feed stops updating is closed after 5 h instead of staying "live".

This is an undocumented public feed. It's fine for development, but ESPN can change or block it at any time, so use a licensed data provider in production. It rejects unrecognised custom user agents, so the client sends httpx's default identifier; it never pretends to be a browser.

For an official second source, add a free [football-data.org](https://www.football-data.org/client/register) key with `UBF_FOOTBALL_DATA_API_KEY`. Fixtures from both providers are merged into one match per game.

### Match details and league tables

Open a match and, where ESPN publishes them, you get **line-ups** on a pitch (formation, shirt numbers,
goals, cards, who came off), a **timeline** of goals, cards and substitutions with the running score,
**team stats** and each side's **last five results**. Competition pages carry the **league table**, with
qualification and relegation colours, group or conference splits, and your followed teams in bold.

Both are fetched on demand when a page is opened, never on a schedule, and cached by how live the data
is: 30 s during a match, 2 min in the three hours before kick-off (when line-ups drop), 5 min just after
full time, and 6 h for older matches. Tables are cached for 5 min. A failed lookup is cached for a
minute and the previous copy is served meanwhile, so a blip never empties the page.

### Following teams, reminders and the calendar

- **My teams:** follow a club or country from its page, a tile or a table row. Followed teams are stored
  in your browser only, with no account, and their matches lead the home page and get their own page.
- **Add to calendar:** every upcoming match offers Google Calendar or an `.ics` file with a reminder 15
  minutes before kick-off.
- **Internationals:** a filter for national-team competitions (Nations League, friendlies, qualifiers),
  which are also kept out of the "Other" bucket.

### Languages and time zones

The interface is available in **English, Spanish, Portuguese, French, German and Italian**, chosen from
the globe button in the header (or the menu on a phone) and remembered in the browser. The language is
detected from the browser on a first visit. Each language is a separate chunk, loaded only when picked.
Dates, numbers and relative times use the viewer's regional variant of that language.

Kick-off times follow a **time zone picker** in the same menu: it defaults to the device's zone and can
be set to any IANA zone, which every date on the site then respects, including the day a match is
grouped under. Team names, competition names and the names of countries come from the data and are not
translated, except country names, which use the browser's own localized list.

`frontend/src/lib/locales/en.ts` is the source of truth: every other locale is type-checked against it,
so a missing or misspelled key fails `npm run build`.

### Team banners, club facts and competition logos

- **Banners:** each team page shows a freely licensed photo of the club's home ground from **Wikimedia Commons**. The author and licence (CC BY / CC BY-SA / CC0) are shown on the banner and link to the original file, as those licences require.
- **How the photo is found** (`app/media/service.py`):
  - **Stadium name:** from TheSportsDB, or else the venue of the team's home matches.
  - **Wikipedia lookup:** first an exact article title. Then a search that ranks venues by how many of the stadium's and club's words appear in the article's title, description and intro, which handles sponsor names like "Allianz Stadium Turin" → Juventus Stadium. As a last resort, a "<club> stadium" search that only accepts articles naming the club.
  - **Photo filter:** only wide, sharp (≥1200 px), freely licensed photos are used. If the article's lead photo doesn't qualify, its other photos are checked.
- **Club facts:** founding year, stadium, capacity and website come from **TheSportsDB**'s free API (key `123`, set `UBF_SPORTSDB_KEY`). Reserve, youth and B sides are never matched to the senior club.
- **When lookups run:** in the background, popular teams with fixtures coming up first, at polite rates (TheSportsDB ~27/min, Wikimedia ~3/s). A team is also looked up on the spot when its page is opened. Results are refreshed monthly; teams without a photo are retried weekly and network failures after 6 hours.
- **No photo:** the banner falls back to the club colour with the stripe texture.
- **Wikimedia's User-Agent policy:** it requires a contact URL or email in the User-Agent. Set `UBF_CONTACT` to a real one before deploying; it defaults to this app's `/about` page.
- **Competition logos:** real logos come from ESPN's feed for every competition. The coloured monogram is only a fallback.

### Demo mode (optional, offline)

`UBF_DEMO_MODE=true` swaps real fixtures for a deterministic synthetic schedule (a kickoff every 45 minutes across eight competitions, so there are always live, upcoming and finished matches). It also enables two simulated third-party sources served by the backend under `/mock-sources`, whose links exercise every health state: redirect chains, meta-refresh, flaky, slow, rate-limited and dead. Turning demo mode back off purges the synthetic matches and demo sources on the next start. The header shows a **Demo** badge while it's on.

### Sources: free, official streams worldwide

The **free streams** connector (`connectors/api/free_streams/registry.json`) lists free, legal ways to watch, researched for 2026-27. Each entry records the competition, the countries it's available in, the access terms (free, free sign-up, TV licence) and whether it shows every match or selected ones. Every entry cites its source so it can be re-checked each season. Entries are verified before being added: a channel is only listed when its own published schedule shows full live matches, so highlights-only channels (LaLiga, Serie A, the Premier League, UEFA) and commentary-only watch-alongs are deliberately left out. The list includes:

| Where | Free and official | Competitions |
|---|---|---|
| Brazil | CazéTV, ge tv, Canal GOAT (YouTube) | La Liga (every match), Premier League, Ligue 1, Bundesliga, Serie A, Série A, Saudi Pro League, WSL, NWSL, Concacaf Nations League |
| 55 territories incl. India, Pakistan, Bangladesh, Sri Lanka, Nepal, UK, Ireland, Japan, France, the Baltics and Oceania | Canal GOAT (YouTube) | Libertadores, Sudamericana |
| Worldwide except North & Central America | Concacaf (YouTube) | Concacaf Nations League |
| Worldwide | Barclays WSL, J.LEAGUE International (outside Japan), The AFC Hub (YouTube); NWSL+ (outside the US, every match) | WSL, J1 League, AFC Champions League, NWSL |
| USA | CBS Sports Golazo Network | Europa & Conference League, Serie A, NWSL, WSL, Brasileirão, SPFL, Argentina, AFC, Concacaf |
| Ireland / Turkey / Belgium / Luxembourg | Virgin Media Play, RTÉ Player / tabii / VTM GO, RTL Play / RTL Play | Champions League (selected) |
| Spain, Germany, France, Italy, Portugal, Finland, UK | RTVE, ARD/ZDF, TF1+, RaiPlay, RTP, Yle, ITVX | Their own national team in the Nations League |
| UK, Greece, Australia, China, Argentina, Mexico, France | BBC iPlayer, Bundesliga YouTube, Destination Calcio, ANT1+, 9Now, CCTV-5, TV Pública, Azteca 7, Zack Nani | WSL, 2. Bundesliga, Serie B, Europa/Conference, Premier League, LPF, Liga MX, Saudi Pro League |

How the site uses it:
- **Your country first:** the site picks the viewer's country from the browser (timezone, then language), shows a "Watching from" picker on match pages, and orders sources so what's watchable *here* comes first. Sources only available elsewhere sit in a collapsed "in other countries" section. In production, Cloudflare's `CF-IPCountry` header is used when the browser doesn't send a country.
- **One-click watch:** when the best source for the viewer is free, available in their country, and shows every match (or is confirmed for this one), match cards and the hero get a **Watch** button that opens the stream directly. "Selected matches" sources say so and link to the channel ("Check channel") rather than claiming the match is on.
- **Exact YouTube videos:** set `UBF_YOUTUBE_API_KEY`, a free YouTube Data API v3 key (about 3 quota units per channel per 10 minutes). YouTube entries then link straight to the match's live or scheduled video, marked "On for this match", instead of to the channel. Without a key nothing breaks: those entries fall back to the channel page and say "Check channel".
- **Geo-blocked players:** many broadcaster players refuse connections from outside their country. For these sources a timeout or refused connection shows as "Couldn't verify from our location" with an **Open source** button, not "Offline".

The sample paid-broadcaster list (`connectors/api/official_broadcasters/`) is tagged as subscription with its regions. Club crests for the seeded teams come from the football-data.org crest CDN; feed teams use ESPN's crests.

---

## One source of truth for the API

The frontend's types are **generated from the backend**, not written by hand:

```
backend/app/api/schemas.py  →  frontend/openapi.json  →  frontend/src/lib/api-schema.ts
                                                              ↑
                                              frontend/src/lib/types.ts (aliases)
```

```bash
cd frontend && npm run types:api
```

`types.ts` is nothing but aliases into the generated file, so every component keeps importing
the same friendly names (`Match`, `SourceLink`, `LeagueTable`) while the definitions come from
the Python models. Rename or retype a field in FastAPI and the frontend **stops compiling**
instead of breaking quietly for users. CI regenerates and fails if the committed output is
stale.

Generating this the first time immediately earned its keep. The API was describing several
fields as a bare `string` when it only ever returns a fixed set of values, so those became
`Literal` types in `schemas.py` — `status`, `access`, `coverage`, the media status and the stat
keys. The constraint now lives in one place and reaches the browser automatically. It also
found a live mismatch: `regions` is optional on the API but the frontend assumed it was always
present.

> `openapi-typescript` runs through `npx` rather than as a dependency. It builds its output
> with the TypeScript compiler's AST factory, which exists in TypeScript 5 but not in the 7
> this project uses; installed locally it resolves to the wrong one and crashes.

## Architecture

```
frontend/                React 19 · TypeScript · Vite · Tailwind v4 · Motion · TanStack Query
backend/app/
├── main.py              FastAPI app, lifespan, security headers, SPA serving
├── config.py            All settings (env prefix UBF_)
├── connectors/          SOURCE ENGINE: plug-in connectors
│   ├── base.py          SourceConnector contract + normalized DiscoveredMatch/DiscoveredLink
│   ├── registry.py      Auto-discovers connectors/{web,api,app}/<name>/adapter.py
│   ├── pipeline.py      fetch → parse → normalize → match → store (per-connector isolation)
│   ├── web/demo_listing/        WEB PAGE connector (HTML scraping)
│   ├── api/demo_feed/           API connector (JSON)
│   ├── api/official_broadcasters/  OFFICIAL FEED connector (curated registry)
│   └── app/             Public app endpoints go here
├── match/               MATCH ENGINE
│   ├── normalize.py     "Manchester City F.C." / "Man City" / "MCI" → one canonical form
│   ├── teams.py         Alias directory; resolves or creates teams
│   ├── matcher.py       Associates a source listing with a fixture (teams + kickoff + competition)
│   ├── sync.py          Provider fixtures → de-duplicated matches
│   └── providers/       espn (default), football-data.org, demo
├── resolver/            Redirect resolution (301/302/303/307/308 + meta refresh) and SSRF guard
├── validator/           Reachability checks, health cycle, reliability history
├── scheduler/engine.py  Adaptive scheduling for fixtures, discovery and health
├── database/            SQLAlchemy models (SQLite by default, Postgres via asyncpg), seed data
├── demo/                Synthetic schedule + mock third-party sources
└── api/                 Public + admin REST routes
```

### Ingestion pipeline (PRD §33)

`FETCH SOURCE → PARSE → NORMALIZE TEAMS → NORMALIZE KICKOFF → MATCH AGAINST DATABASE → EXTRACT LINKS → RESOLVE REDIRECTS → VALIDATE → STORE → UI polls`

- **Isolation:** each connector runs in its own try/timeout. A crash, HTTP error or timeout is recorded against that source (`crawl_runs`, `sources.last_error`) and the others carry on. This is covered by a test.
- **Unmatched listings are never invented.** If a source lists a fixture we don't know, it's counted and shown in the crawler log.
- **Expiry:** links a source stops listing are marked `EXPIRED / NO_LONGER_AVAILABLE`. If a connector suddenly returns *nothing*, that's treated as a broken parser: existing links are kept and the run is flagged `EMPTY_RESULT`.

### Scheduling (PRD §34)

| Job | Cadence |
|---|---|
| Fixture sync | every 15 s while matches are live (demo), ≥60 s for football-data.org, 10 min idle |
| Source discovery | 2 min when live/kickoff within 30 min · 5 min within 3 h · 15 min otherwise |
| Link health | tick every 10 s; per link: 30 s live · 2 min near kickoff · 15 min otherwise; per-source floor (official pages: 30 min); exponential backoff on repeated failures |

Every unique URL is checked once per cycle even if it's listed for many matches. Concurrency is capped globally (8) and per host (2).

### Link states

| Backend status | UI | Meaning |
|---|---|---|
| `DISCOVERED`, `RESOLVING` | 🟡 Checking | Not checked yet / check in progress |
| `VALID` | 🟢 Working | Destination returned 2xx after redirects |
| `RESOLVED` | ⚪ Not verified | Reachable, but 401/403 or a region redirect. We don't try to get around access controls, so we say we can't verify it. |
| `INVALID`, `ERROR` | 🔴 Offline | 404/410, soft-404 markers, timeouts, 5xx, 429, DNS failures, blocked by policy |
| `EXPIRED` | hidden | No longer listed, or the match ended |

Quality (e.g. "1080p") is shown only when verified, which in practice means an HLS master playlist that declares its renditions.

**Watch now** goes through `/api/links/{id}/go`. That endpoint records the click (for the "source → destination success" metric) and 302s to the resolved destination if it was verified in the last 15 minutes, otherwise to the original URL. It only ever redirects to stored link URLs, so it can't be used as an open redirect.

---

## Adding a source connector

1. Create `backend/app/connectors/<web|api|app>/<your_source>/__init__.py` and `adapter.py`.
2. Subclass `SourceConnector`, implement `discover(ctx)`, return `DiscoveredMatch` objects, and export it as `CONNECTOR`:

```python
from app.connectors.base import ConnectorContext, DiscoveredLink, DiscoveredMatch, SourceConnector
from app.database.models import ConnectorType

class MySource(SourceConnector):
    key = "my-source"
    name = "My Source"
    connector_type = ConnectorType.API
    domain = "api.example.com"
    min_check_interval = 60                       # politeness floor for health checks
    offline_markers = ("this stream has ended",)  # soft-404 phrases

    async def discover(self, ctx: ConnectorContext) -> list[DiscoveredMatch]:
        data = (await ctx.get("https://api.example.com/events")).json()   # goes through the SSRF guard
        return [
            DiscoveredMatch(home=e["home"], away=e["away"], kickoff=..., competition=e.get("league"),
                            links=[DiscoveredLink(url=e["url"], label="Main", language="English")])
            for e in data["events"]
        ]

CONNECTOR = MySource
```

That's all. The registry picks it up on restart. Matching, resolution, validation, health history, the admin monitor and the UI all come from the shared pipeline. Use `ctx.matches` if your source is keyed off our own fixtures, and set `match_id` to skip fuzzy matching.

Before adding a connector, check the source's terms and the rights situation in your jurisdiction (see Compliance).

---

## API

Public (rate-limited per client IP):

```
GET /api/home                      featured match (live | next | always_on), live, competitions, teams
GET /api/matches                   ?status=live|upcoming|finished|all &date_from &date_to &competition &team &teams &limit &offset
                                   competition=internationals → national-team competitions; teams=a,b,c → My teams
GET /api/matches/live
GET /api/matches/upcoming          ?days &competition
GET /api/matches/{id|slug}
GET /api/matches/{id|slug}/sources sorted: working (fastest, official first) → checking → unverified → offline
GET /api/matches/{id|slug}/details line-ups, timeline, team stats, recent form (from ESPN, when available)
GET /api/matches/{id|slug}/calendar.ics  ?alarm=15     one match, with a reminder
GET /api/competitions/{slug}/table league table: groups, qualification notes, our team links
GET /api/links/{id}/go             click-through redirect
GET /api/competitions · /api/competitions/{slug}
GET /api/teams · /api/teams/{slug}
GET /api/search?q=arsenal          teams (incl. aliases like "spurs"), competitions, matches
GET /api/meta
```

Admin (header `X-Admin-Token`):

```
POST /api/sources/run[?source=key]   POST /api/links/validate {link_ids?, force?}   POST /api/matches/sync
GET  /api/admin/overview | sources | runs | links | matches     PATCH /api/admin/sources/{key} {enabled}
```

Interactive docs: http://127.0.0.1:8000/docs

---

## Deploying

The image is self-contained: one process serves the API and the built frontend, listens on
`$PORT` when the platform sets one, and answers `/healthz` for health checks.

```bash
docker build -t ubf .
docker run -p 8000:8000 -v ubf-data:/data --env-file backend/.env ubf
```

Anywhere that runs a container works — Render, Railway, Fly.io, Google Cloud Run, a plain VPS.
Set at least:

| Variable | Why |
|---|---|
| `UBF_ADMIN_TOKEN` | Protects `/admin`. A random one is generated and logged if unset |
| `UBF_CONTACT` | Wikimedia requires a contact in the User-Agent for banner photos |
| `UBF_PUBLIC_BASE_URL` | Used in calendar invitations |
| `UBF_CORS_ORIGINS` | Only if the frontend is served from another domain |
| `UBF_YOUTUBE_API_KEY` | Optional: links YouTube sources to the exact match video |
| `UBF_TRUST_PROXY_HEADERS` | `true` behind a proxy that sets `X-Forwarded-For`, so rate limiting sees real client IPs |

**Storage.** SQLite lives at `/data/ubf.db`, so mount a persistent volume there. Without one
the database resets on every deploy — survivable, since fixtures re-sync from ESPN, but banner
lookups and link history start over. For more than one instance, move to Postgres with
`UBF_DATABASE_URL=postgresql+asyncpg://…` (`requirements-postgres.txt`) — the in-process cache
and rate limiter are per-instance, so they want Redis before scaling out too.

**Before going live,** read the Compliance section. Fixtures come from an undocumented ESPN
endpoint that is fine for development but is not a licensed feed.

## Security (PRD §47)

- **SSRF guard** (`resolver/ssrf.py`) on every outbound request for links *and* source listings: http/https only, no embedded credentials, ports 80/443, and any host resolving to loopback, RFC1918, link-local (incl. `169.254.169.254` metadata), CGNAT, multicast, reserved or IPv4-mapped/6to4/Teredo-wrapped private space is refused. **Every redirect hop is re-checked**, and the connected peer IP is verified after connect to narrow the DNS-rebinding window. The checker runs with `trust_env=False` so proxies can't hide the peer. For production, also run it behind an egress firewall. The only exemption is the backend's own `host:port` in demo mode (or what you list in `UBF_RESOLVER_ALLOW_HOSTS`).
- **Rate limiting** on matches, sources and search.
- **Sanitization:** all third-party text is stripped of markup, control and bidi characters and length-bounded before storage. React escapes on render, and only http(s) URLs are ever used as link targets.
- **Secrets** live server-side (`.env`). The admin token is compared in constant time.
- Security headers (`nosniff`, `DENY` framing, referrer policy) and `no-store` on API responses.

## Compliance (PRD §48)

The platform is built to prefer official APIs and licensed destinations. The bundled official-broadcasters connector is that model. The resolver follows ordinary redirects only: no script execution, no CAPTCHA solving, no credential replay, no DRM or paywall circumvention, no re-streaming. Region-locked and login-gated destinations are reported as "not verified" rather than worked around. The broadcaster registry is a **sample**; rights change every season and by territory. Linking and aggregation law varies by jurisdiction and content, so get legal review before a production deployment.

---

## MVP status vs. PRD §53

| Area | Status |
|---|---|
| Homepage: brand, dynamic hero (live / next / "Football is always on"), live grid, upcoming with day tabs + competition filters, popular competitions & teams, dynamic section order (≥4 live → live first), polished empty/loading/error states | ✅ |
| Match page: status, minute, score, crests, competition, venue, referee (when known), kickoff, available sources with health, last-checked, latency, language, reliability, auto-refresh | ✅ |
| Multiple sources per match; health states; redirect resolution; failed sources marked; one broken source can't break others | ✅ (tested) |
| Modular connectors; normalization across naming differences; duplicate merge; scheduled crawling; health checks; persisted source state | ✅ (tested) |
| Search, schedule ("View all") with date/status/competition/team filters, competition & team pages, light/dark theme, responsive with mobile bottom nav, subtle motion with reduced-motion support | ✅ |
| Match details: line-ups on a pitch, timeline, team stats, recent form; league tables on competition pages | ✅ (tested) |
| My teams (followed in-browser), kick-off reminders, `.ics` download and subscribable calendar feed, Internationals filter | ✅ (tested) |
| Six languages, time zone picker, WCAG 2.1 AA checked automatically on every page type | ✅ (tested) |
| Admin: source monitor (run/disable), live match monitor, link health, crawler logs, metrics (validation success rate, latency, click-through) | ✅ |

**Not in this MVP:**

- **Redis:** the cache and rate limiter are in-process. Fine for one API worker; move them to Redis before scaling out.
- **Alembic migrations:** tables are created with `create_all`. Add Alembic before the schema changes in production.
- **Server-side rendering:** match, team and competition pages have crawlable URLs and per-page titles and descriptions, but this is a client-rendered SPA. Use SSR or prerendering if SEO matters.
- **Accounts:** followed teams, language, time zone, country and theme live in the browser, so they don't
  follow you to another device. Accounts and push notifications are the next step.
- **Phase 2/3 features:** push notifications and user-submitted sources.
