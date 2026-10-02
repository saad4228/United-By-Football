# Understanding this codebase

A guide from no web-development knowledge to knowing what every part of this project does
and why. Roughly 6,100 lines of Python and 9,300 lines of TypeScript, explained in the order
that makes them easiest to learn.

**How to use it.** Read Parts 1–3 first; they're short and everything later depends on them.
Then work through Parts 4–6 with the files open beside you. Part 9 is a day-by-day plan if you
want structure, and Part 10 is interview practice.

---

## Part 1 — What a web application actually is

Skip this if you already know it.

### Two computers, not one

When you open a website, **two** computers are involved.

The **client** is the visitor's browser. It draws things on screen and reacts to clicks. It can
only do what the person's own device can do.

The **server** is a computer you control that is always on. It holds the database, keeps
secrets, and talks to other companies' services.

They communicate over **HTTP**: the browser sends a *request*, the server sends a *response*.

### The request

A request has a **method** and a **path**:

| Method | Means |
|---|---|
| `GET` | "Give me something" — reading |
| `POST` | "Here is something" — creating or triggering |
| `PATCH` | "Change part of this" |

So `GET /api/matches` means "give me the matches."

The response carries a **status code**: `200` fine, `404` not found, `401` not allowed,
`500` the server broke.

### JSON

Servers reply with **JSON** — text that represents structured data:

```json
{ "name": "Arsenal", "country": "England", "founded": 1886 }
```

Both Python and JavaScript can read and write it, which is why it's the common language
between the two halves.

### An API

A set of paths a server answers is an **API**. This project's API includes `/api/matches`,
`/api/teams`, `/api/competitions`. The frontend knows these paths and nothing else about how
the backend works — that separation is the point.

### A database

Data that must survive a restart lives in a **database**: tables of rows and columns, like
spreadsheets that can reference each other. This project has tables for teams, matches,
competitions, sources and links.

### Why split frontend and backend

**Secrets.** Your YouTube API key lives on the server. If it were in the browser, every
visitor could read it from the page source.

**Trust.** Anything in the browser can be edited by the visitor. Anything the server decides
cannot.

---

## Part 2 — What this project does

Four jobs, in order:

1. **Collect fixtures** — fetch matches, kick-off times, live scores, line-ups and league
   tables from ESPN's public feed.
2. **Collect viewing sources** — know which legal service shows which match in which country.
3. **Match them together** — the hard part. ESPN says "Manchester City", a broadcaster says
   "Man City". Same team.
4. **Verify continuously** — re-check every viewing link and report an honest status.

### The journey of one match

```
ESPN's API
   │  fixtures, scores, teams
   ▼
match/providers/espn.py        fetches and parses
   ▼
match/sync.py                  normalises names, removes duplicates, saves
   ▼
Postgres (or SQLite)           stored
   ▼
api/routes/public.py           serves it as JSON at /api/matches
   ▼
frontend/src/lib/api.ts        the browser asks for it
   ▼
frontend/src/pages/            React draws it on screen
```

Meanwhile, separately and on their own timers:

```
connectors/    discover viewing links for known matches
resolver/      follow redirects to find where a link really goes
validator/     check each link still works, record the result
media/         find a stadium photo and club facts for each team
```

---

## Part 3 — The repository map

```
backend/           Python server
  app/
    main.py              starts everything
    config.py            every setting
    api/                 the HTTP endpoints
    database/            tables and connections
    match/               MATCH ENGINE  — fixtures, teams, dedup
    connectors/          SOURCE ENGINE — plug-in viewing sources
    resolver/            redirect following + SSRF protection
    validator/           link health checking
    scheduler/           background jobs
    media/               team photos and club facts
    utils/               small shared helpers
    demo/                fake data for offline work
  tests/                 127 tests
  scripts/               one-off tools

frontend/          React browser app
  src/
    main.tsx             starts everything
    App.tsx              which URL shows which page
    pages/               one file per screen
    components/          reusable pieces of UI
    lib/                 non-visual logic
  e2e/                   26 browser tests

Dockerfile         builds both halves into one image
docs/              you are here
```

Two mental anchors:

- **Backend = `main.py` → everything else.**
- **Frontend = `main.tsx` → `App.tsx` → a page → components.**

---

## Part 4 — The backend, file by file

Read in this order. Each section says *what it is*, *why it exists*, and *what to notice*.

### 4.1 `app/config.py` — every setting

One class, `Settings`, listing every configurable value with a default. Values can be
overridden by environment variables prefixed `UBF_`, so `UBF_ESPN_ENABLED=false` turns off
the ESPN provider without touching code.

**Why it matters:** nothing in the codebase reads environment variables directly. There is
exactly one place to look to know how the app can be configured.

### 4.2 `app/database/models.py` — the shape of the data

Each class is a database table. `Team`, `Match`, `Competition`, `Source`, `StreamLink`,
`HealthCheck`, `CrawlRun`, `TeamMedia`, and the `*ExternalRef` tables.

**Notice `UTCDateTime`.** A small wrapper that always stores times as naive UTC and always
returns them timezone-aware. Without it, SQLite and Postgres disagree about timezones and
bugs appear only in production.

**Notice `TeamExternalRef`.** Teams are tracked by the provider's own ID, not by name. If a
club renames itself, it stays the same row.

### 4.3 `app/database/session.py` — connecting

Creates the database engine and hands out sessions (a session is one unit of work).

Two things worth reading closely:

- **`normalize_database_url()`** — hosting providers hand out connection strings in several
  spellings. This accepts all of them. It exists because a real deployment failed:
  SQLAlchemy read a plain `postgresql://` as a driver that wasn't installed.
- **`_add_missing_columns()`** — when the models gain a new optional column, this adds it to
  an existing database. A stand-in for proper migrations, which the README lists as a known gap.

### 4.4 `app/main.py` — starting up

`create_app()` builds the application: security headers, CORS, rate limiting, the routers,
`/healthz`, and serving the built frontend.

**The `lifespan` function is the important part.** It runs once at startup — create tables,
seed reference data, start the background scheduler — and once at shutdown to stop everything
cleanly.

### 4.5 `app/api/` — the endpoints

| File | Role |
|---|---|
| `schemas.py` | The exact shape of every response, as Pydantic models |
| `queries.py` | Shared database queries and the logic for turning rows into responses |
| `routes/public.py` | Everything visitors use |
| `routes/admin.py` | Everything behind the admin token |
| `deps.py` | Reusable pieces: database session, rate limiting, admin check |

**`schemas.py` is the contract.** The frontend's TypeScript types are generated from these,
so changing one here changes the frontend's types too. Notice the `Literal` types —
`MatchStatus`, `Access`, `Coverage` — which say "only these exact values are possible."

**In `queries.py`, read `availability()` and `one_click()`.** They decide whether a source is
watchable where the visitor is, and whether to show a direct "Watch" button. Regions use `*`
for worldwide and `!US` to exclude a country.

### 4.6 `app/match/` — the match engine

This is the most interesting part of the backend.

**`normalize.py`** — turns "Manchester City F.C." into a canonical form. Lowercases, strips
punctuation, removes filler words like FC and AFC.

**`teams.py`** — `TeamDirectory` resolves a name coming from a provider into a team row:
first by the provider's ID, then by name, then by alias, with a country check so England's
Arsenal and Argentina's don't merge. Creates the team if genuinely new.

**`matcher.py`** — fuzzy matching for connectors: given "Man City vs Arsenal, 7pm", find
which stored fixture that is.

**`sync.py`** — takes fixtures from a provider and saves them. `FixtureSyncer.upsert()` is
where deduplication lives.

> **The bug worth knowing.** Two fixtures with the same teams close together used to merge
> into one. Barcelona and Real Madrid played twice in 36 hours — league, then cup — and the
> site showed one match. The fix: two fixtures from the *same* provider are always different
> matches; only merge across *different* providers. That's the `self.owned` set.

**`providers/`** — each file knows how to talk to one data source and returns the same
`NormalizedFixture` shape, so the rest of the code doesn't care where data came from.

- `espn.py` — the default. Read `fetch()` and notice the caching: each league's calendar is
  read first so only days with real fixtures are requested, and each page is cached for 30s
  if a match is live, 5 minutes for today, an hour for future days.
- `espn_details.py` — line-ups, timeline, stats, league tables. Fetched on demand.
- `football_data.py` — an optional second provider.
- `demo.py` — synthetic fixtures for working offline.

### 4.7 `app/connectors/` — the source engine

Where viewing links come from. Designed so adding a source needs no changes to existing code.

**`base.py`** — the contract. A connector subclasses `SourceConnector` and implements
`discover()`.

**`registry.py`** — finds connectors automatically by scanning
`connectors/{web,api,app}/*/adapter.py` for a `CONNECTOR` export.

**`pipeline.py`** — runs one connector inside an error boundary with a timeout, then stores
what it found. **This is the fault isolation:** if a connector crashes, the failure is
recorded against that source and every other connector carries on.

> Also notice the empty-result guard: if a connector suddenly returns *nothing*, that's
> treated as a broken parser rather than "all links are gone," so a website redesign can't
> wipe your data.

**`api/free_streams/`** — the real one. `registry.json` lists 43 verified free, legal sources
with their competitions, countries, access terms and coverage. `youtube.py` uses the YouTube
API to find the exact video for a match.

### 4.8 `app/resolver/` — following links safely

**`ssrf.py` is the most security-relevant file in the project. Read it properly.**

SSRF means tricking *your server* into making requests for an attacker. This app is unusually
exposed because its job is fetching URLs that came from outside.

The classic attack: submit `http://169.254.169.254/`. On a cloud server that address returns
the machine's own credentials.

`URLGuard` blocks: non-HTTP schemes, embedded credentials, unusual ports, and any host
resolving to loopback, private, link-local or reserved addresses. Crucially it **re-checks
every redirect hop** and **verifies the IP actually connected to**, which closes the
DNS-rebinding window.

**`resolver.py`** — follows redirects (including HTML meta-refresh) to find a link's real
destination, with the guard applied at each step.

### 4.9 `app/validator/` — is this link alive?

Checks each link and maps the result to an honest status. The interesting judgement is in
`health.py`: a `401` or `403` becomes **"not verified"**, not "offline", because it usually
means "wrong country" or "needs login" — and this app never tries to get around access
controls.

### 4.10 `app/scheduler/engine.py` — the background jobs

`Engine` owns the shared HTTP clients and runs four loops: fixtures, discovery, health,
maintenance, plus media.

**The idea worth understanding:** frequency follows how live the data is. Matches in progress
are re-checked every 30 seconds; quiet periods back off to minutes. A naive version would poll
everything constantly and be both wasteful and rude to the services it depends on.

### 4.11 `app/media/service.py` — stadium photos

Finds a freely licensed photo of each club's home ground on Wikimedia Commons, plus club
facts from TheSportsDB. Stores the author and licence so the banner can credit them, which
those licences require.

Deliberately slow — one team every four seconds — to stay polite to both APIs.

### 4.12 `app/utils/`

| File | Role |
|---|---|
| `time.py` | `utcnow()` — one place that defines "now" |
| `text.py` | Strips markup and control characters from third-party text |
| `ratelimit.py` | In-process rate limiting |
| `ics.py` | Writes calendar files for "Add to calendar" |

---

## Part 5 — The frontend, file by file

### 5.1 How React works, briefly

A **component** is a function returning a description of UI:

```tsx
function TeamName({ team }) {
  return <span>{team.name}</span>;
}
```

That `<span>` syntax is **JSX** — HTML-like code inside JavaScript, converted to real
JavaScript at build time.

**State** is data that changes; when it changes, React redraws that component. **Props** are
values passed into a component from its parent.

### 5.2 `main.tsx` — the entry point

Loads fonts and styles, applies the saved language and timezone *before* the first render so
nothing flashes in English, then wraps the app in providers.

A **provider** makes something available to every component below it without passing it
through every layer: the query client, theme, country, preferences, followed teams.

### 5.3 `App.tsx` — routing

Maps URLs to pages. `/match/:slug` means "anything after /match/ is a parameter."

Most pages are **lazily loaded** — their code downloads only when visited, so opening the home
page doesn't download the admin dashboard.

### 5.4 `lib/` — the logic

| File | Role |
|---|---|
| `api.ts` | Every call to the backend, in one place |
| `api-schema.ts` | **Generated** from the backend. Never edit |
| `types.ts` | Friendly names aliasing the generated types |
| `i18n.tsx` | Translation: `t()`, plus `tn()` for plurals and `tr()` for embedded elements |
| `time.ts` | All date formatting, timezone-aware |
| `prefs.tsx` | Language and timezone, saved in the browser |
| `myteams.tsx` | Followed teams, saved in the browser |
| `country.tsx` | Detects the visitor's country for source availability |
| `colors.ts` | Team colours, with contrast handling |
| `images.ts` | Requests crests at the size actually drawn |
| `hooks.ts` | Small reusable behaviours |

**`types.ts` is worth understanding.** It contains no definitions of its own — every line
aliases something generated from the backend's OpenAPI document. Rename a field in Python and
the frontend stops compiling.

### 5.5 `components/` and `pages/`

A **page** is a whole screen; a **component** is a piece reused across pages.

| Page | Screen |
|---|---|
| `HomePage` | Hero, live matches, upcoming, competitions, teams |
| `MatchPage` | One match: score, sources, line-ups, stats |
| `SchedulePage` | All matches with filters |
| `DirectoryPages` | Competitions, teams, search, about, 404 |
| `MyTeamsPage` | Followed teams |
| `AdminPage` | The monitoring dashboard |
| `SecretPage` | The hidden vault |

Notable components: `MatchCard` (used everywhere), `SourceCard` (one viewing source with its
health), `MatchDetails` (line-ups on a pitch, timeline, stats), `LeagueTable`, `TeamBanner`.

### 5.6 How data reaches the screen

The project uses **TanStack Query**, which handles fetching, caching, refetching and
loading/error states:

```tsx
const home = useQuery({
  queryKey: ["home", country],      // identity of this data
  queryFn: () => api.home(country), // how to fetch it
  refetchInterval: 15_000,          // refresh every 15s
});
```

`queryKey` is the important idea: include everything the result depends on. Because `country`
is in the key, changing country automatically refetches rather than showing stale data.

---

## Part 6 — The five parts worth explaining in an interview

### 1. The connector architecture

Each viewing source is a self-contained folder, discovered automatically at startup. Adding one
requires no changes to existing code — **open for extension, closed for modification**.

Each runs inside its own error boundary with a timeout, so one broken source can't affect the
others. There's a test that deliberately crashes a connector and asserts the rest still work.

### 2. Team matching and deduplication

Layered: normalise the name → check known aliases → prefer the provider's own ID → guard by
country. Then merge the same fixture reported by different providers, but never two fixtures
from the same provider.

Tell the Clásico story (Part 4.6). Concrete bugs are more convincing than descriptions.

### 3. SSRF protection

See Part 4.8. The short version: this app fetches URLs that came from strangers, so every
outbound request is checked, every redirect re-checked, and the connected IP verified.

### 4. Generated API types

The frontend used to describe the backend's data from memory, with nothing enforcing it. Now
the types are generated from the backend's OpenAPI document, so a rename in Python becomes a
frontend compile error. CI regenerates and fails if what's committed is stale.

It found two real problems immediately: fields typed as plain `string` that only ever held a
few values, and an optional field the frontend assumed was always present.

### 5. Type-safe translations

English is the source of truth. Every other language is *typed against it*, so a missing or
misspelled key fails `npm run build`. Translations cannot silently rot.

---

## Part 7 — Testing

```bash
cd backend && .venv/Scripts/python -m pytest        # 127 tests
cd frontend && npm run build && npm run test:e2e    # 26 tests
```

**Backend tests** never touch the network. `conftest.py` routes all HTTP back into the app
itself, so results never depend on someone else's server.

**Browser tests** (Playwright) start their own backend in demo mode with a throwaway database,
block every request leaving the machine, and fail on *any* console error. They run at desktop,
Android and iPhone sizes, and check each page with axe-core for accessibility.

Both run in CI on every push.

> **A real flaky test and its fix.** The hidden-page test clicked an icon ten times and
> occasionally failed. The clock reset its count if clicks were more than 1.5s apart, and under
> parallel load a single click sometimes exceeded that. Widening the window to 3s fixed it —
> still a long pause for a deliberate click.

---

## Part 8 — Deployment

One Docker image: Node builds the frontend, then the Python image serves it alongside the API.
Node never ships to production.

Live on Render's free tier with Supabase Postgres and a cron ping every 10 minutes so the
instance doesn't sleep.

**Two things learned the hard way**, both now handled in code or documented:

1. SQLAlchemy reads a plain `postgresql://` as a driver that wasn't installed. Fixed by
   normalising any connection string the host gives.
2. The **first fixture sync against a hosted database takes 20–30 minutes** — thousands of
   round trips for ~780 fixtures. It looks exactly like a failure: empty API, no completed run,
   no errors. It is committing, not stuck.

---

## Part 9 — A five-day plan

**Day 1 — the shape.** Read Parts 1–3. Run it locally. Open the site and click everything.
Then open `/docs` on the running backend and try an endpoint.

**Day 2 — follow one request end to end.** Open the home page with the browser's Network tab
open. Find the `/api/home` request. Then find in `routes/public.py` where that is answered,
and in `HomePage.tsx` where it's displayed. *Trace one piece of data from database to pixel.*

**Day 3 — the match engine.** Read `normalize.py`, `teams.py`, `sync.py`. Then run
`pytest tests/test_matching.py -v` and read the tests — they're the clearest description of
what the engine promises.

**Day 4 — break things.** Change something small and watch what fails. Rename a field in
`schemas.py` and run `npm run build`. Delete a line in `sync.py` and run the tests. *Nothing
teaches a codebase like breaking it on purpose.*

**Day 5 — explain it out loud.** Not reading — talking, to a wall. The gap between
understanding and explaining only closes by speaking.

---

## Part 10 — Interview questions, with answers

**"Walk me through the architecture."**
> Python FastAPI backend, React frontend, Postgres. The backend fetches fixtures from ESPN,
> normalises and stores them, and serves a REST API. It also runs background jobs: discovering
> viewing sources, checking those links are alive, and fetching team photos. The frontend is a
> single-page app served by the same process.

**"What was the hardest problem?"**
> Matching teams across sources that name them differently, and the deduplication bug where two
> fixtures between the same teams in the same week got merged into one. *(Tell the Clásico story.)*

**"Why FastAPI?"**
> It's async-first, and this app spends most of its time waiting on other people's APIs. Async
> lets hundreds of link checks run concurrently instead of one at a time.

**"How do you handle a source going down?"**
> Three layers. Each connector runs isolated with a timeout. Failures are recorded per source
> with backoff. And if a connector returns nothing at all, that's treated as a broken parser
> rather than "everything is gone," so existing links are kept.

**"How do you know it works?"**
> 153 automated tests in CI. The backend tests don't touch the network, and the browser tests
> block external requests and fail on any console error.

**"What would you do differently?"**
> A licensed data provider instead of ESPN's public feed, Alembic for migrations, Redis if it
> ever needed more than one instance, and server-side rendering if SEO mattered.

**"Did you use AI?"**
> Yes, heavily, as a pair programmer. I made the architecture and product decisions, did the
> research on broadcast rights, and debugged the deployment myself. *(Then give a concrete
> example — the database driver failure is a good one.)*

---

## Where to look when you're stuck

| Question | File |
|---|---|
| How is X configured? | `backend/app/config.py` |
| What does the API return? | `backend/app/api/schemas.py` |
| Where does this endpoint live? | `backend/app/api/routes/public.py` |
| How are fixtures saved? | `backend/app/match/sync.py` |
| How are sources found? | `backend/app/connectors/pipeline.py` |
| What runs in the background? | `backend/app/scheduler/engine.py` |
| Which URL shows which page? | `frontend/src/App.tsx` |
| How does the frontend call the API? | `frontend/src/lib/api.ts` |
| Where do translations live? | `frontend/src/lib/locales/en.ts` |
