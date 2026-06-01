# 02 — Architecture

## High-level shape

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1 (existing, unchanged)                      │
│                                                                            │
│   crawlers → normalizer → scoring → repository → SQLite (data/fantasy.db)  │
│                                          │                                  │
│                                          ├──────────── read API :8000      │
│                                          │             (ff_pipeline.api)    │
└──────────────────────────────────────────┼─────────────────────────────────┘
                                            │  read-only, in-process reuse of
                                            │  ff_pipeline.repository (models + queries)
                                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    PHASE 2 BACKEND-FOR-FRONTEND (new)                      │
│                         package: ff_dashboard                              │
│                                                                            │
│   repository (reused)  →  analytics/  →  api/  →  HTTP/JSON  :8800         │
│     models, sessions       metrics &      FastAPI routes,                   │
│     read queries           rollups,       pydantic schemas,                 │
│                            in-proc cache  OpenAPI                           │
└──────────────────────────────────────────┬─────────────────────────────────┘
                                            │  fetch (typed client, generated
                                            │  from OpenAPI) + TanStack Query cache
                                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       PHASE 2 FRONTEND SPA (new)                           │
│                         directory: web/                                    │
│                                                                            │
│   React + TypeScript + Vite                                                │
│   ├── design-system/   tokens, primitives (Button, Card, Stat, Table…)    │
│   ├── charts/          chart wrappers (Recharts) with shared theming       │
│   ├── features/        pages composed from primitives (standings, owner…) │
│   ├── lib/             generated API client, query hooks, formatting       │
│   └── app/             router, layout shell, providers                     │
└──────────────────────────────────────────────────────────────────────────┘
```

## The two new deliverables

1. **`ff_dashboard`** — a Python analytics service (backend-for-frontend). It lives in the
   *same repo* as Phase 1, under `src/ff_dashboard/`, and **imports `ff_pipeline.repository`**
   for all database access. It adds an `analytics/` layer (pure functions that turn rows into
   metrics) and its own FastAPI app on a different port. It is read-only.

2. **`web/`** — a React + TypeScript single-page app. Pure presentation. It talks only to the
   `ff_dashboard` API, never to the database and never to the Phase 1 read API directly.

> **Why one repo, two backends?** The BFF needs the SQLAlchemy models and read queries that
> already exist in `ff_pipeline.repository`. Re-implementing them in a separate repo would
> duplicate the schema and invite drift. Keeping `ff_dashboard` beside `ff_pipeline` lets it
> reuse the repository (the sanctioned DB-access boundary) and share tooling (uv, ruff, mypy,
> pytest). Phase 1 code is never modified by Phase 2 except, optionally, additive read
> queries in `repository/queries.py`.

## Why this split (the durable boundary)

- **All business logic is in Python, tested, in one place.** A power-ranking formula, a
  head-to-head tally, "points left on the bench" — each is a pure function in
  `ff_dashboard/analytics/` with a unit test. The frontend cannot disagree with the backend
  because the frontend does no math.
- **The frontend is swappable and polish-friendly.** Because it holds no logic, you can
  restyle, re-lay-out, or even replace the whole SPA without risking a single number.
- **The contract is generated, not hand-synced.** The frontend's API types come from the
  BFF's OpenAPI document. Change a response shape in Python and the TypeScript build flags
  every stale call site.

## Backend module layout (`src/ff_dashboard/`)

```
src/
├── ff_pipeline/          # Phase 1 — unchanged (repository reused by Phase 2)
└── ff_dashboard/
    ├── __init__.py
    ├── settings.py            # pydantic-settings: DB path, host/port, cache TTL
    ├── server.py              # uvicorn entrypoint / app factory wiring
    ├── cache.py               # in-process memoization keyed by latest pipeline_run_id
    │
    ├── engine.py             # create_readonly_engine: WAL + PRAGMA query_only read-only SQLite
    │
    ├── analytics/             # PURE functions: rows -> metrics. No FastAPI here.
    │   ├── __init__.py
    │   ├── common.py          # shared helpers (regular_season_weeks, season/week lookups)
    │   ├── standings.py       # standings, standings-through-week, streaks
    │   ├── power.py           # power ranking model + timeline
    │   ├── matchups.py        # box-score enrichment, optimal lineup, bench points
    │   ├── head_to_head.py    # all-time owner-vs-owner records, rivalry matrix
    │   ├── records.py         # records book / hall of fame rollups
    │   ├── owners.py          # career aggregates, trophy case, trajectories
    │   ├── draft.py           # draft board + pick-value analysis
    │   ├── players.py         # scoring history, ownership, top scorers, positional
    │   ├── teams.py           # team overview, schedule, scoring-trend, transactions
    │   ├── search.py          # global typeahead across owners/teams/players/seasons
    │   └── coverage.py        # /v1/meta coverage flags (seasons scored, gaps)
    │
    ├── api/
    │   ├── __init__.py
    │   ├── main.py            # FastAPI app factory (mirrors ff_pipeline.api.main)
    │   ├── deps.py            # SessionDep / CacheDep (reuse ff_pipeline repository sessions)
    │   ├── schemas.py         # pydantic response models for analytics shapes (additive)
    │   ├── static.py          # optional single-origin SPA mount (serves web/dist)
    │   └── routes/
    │       ├── health.py      # /health + /v1/meta
    │       ├── seasons.py     # /v1/seasons..., /v1/seasons/{id}/standings(+/timeline)
    │       ├── power.py       # /v1/seasons/{id}/power(+/timeline)
    │       ├── matchups.py    # /v1/seasons/{id}/weeks/{w}/matchups, /v1/matchups/{id}/box-score
    │       ├── owners.py      # /v1/owners...  (career, h2h, rivalry-matrix)
    │       ├── records.py     # /v1/records...
    │       ├── draft.py       # /v1/seasons/{id}/draft...
    │       ├── teams.py       # /v1/teams/{id}...
    │       ├── players.py     # /v1/players..., /v1/stats/...
    │       └── search.py      # /v1/search
    │
    └── py.typed
```

> **Error + provenance envelopes are reused from Phase 1, not re-implemented.** `main.py`
> imports `install_error_handlers` from `ff_pipeline.api.errors`, and the routes import
> `build_meta` from `ff_pipeline.api._meta` — so the dashboard has no local `errors.py` /
> `_meta.py`; the envelope and error shapes match Phase 1 verbatim (see `00_SEAM.md`).

> **No `/v1/home` composite.** The home/command-center view is composed **client-side** from
> existing endpoints (`/v1/seasons/{id}/standings`, `/v1/records`, `/v1/seasons/{id}/power`)
> rather than a dedicated server endpoint + `analytics/league.py`. This keeps the BFF surface
> orthogonal (one concern per endpoint) while the SPA still does no math — only orchestration.

The Phase 1 read API (`ff_pipeline.api`) stays exactly as-is. Phase 2 does **not** route
through it; it reuses the repository directly for speed. (Optionally, the BFF can proxy a
couple of trivial passthroughs to keep a single surface — see `03_DATA_ACCESS.md` — but the
default is direct repository reuse.)

## Frontend module layout (`web/`)

```
web/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── tailwind.config.ts
├── postcss.config.js
├── playwright.config.ts
├── e2e/                         # Playwright: journeys.spec.ts + visual.spec.ts
├── src/
│   ├── main.tsx                 # mount + providers (QueryClient, Router)
│   ├── app/
│   │   ├── App.tsx              # route table (React Router); flat switcher-driven routes
│   │   └── shell/              # AppShell, SeasonContext (global switcher), DataAsOf
│   │
│   ├── design-system/           # the durable primitives — one module (see 06_DESIGN_SYSTEM.md)
│   │   ├── index.tsx           # Button, Card, Stat, StatGrid, Badge, Table, Tabs,
│   │   │                        # RecordLine, chips, Skeleton, EmptyState, ErrorState, DataGap…
│   │   └── index.test.tsx
│   │
│   ├── charts/                  # Recharts wrappers w/ shared theme + a11y
│   │   ├── index.tsx           # LineTrend, BarCompare, StackedBreakdown, Heatmap, RankFlow
│   │   └── chartTheme.ts        # reads the CSS tokens
│   │
│   ├── features/                # pages = composition only, no math
│   │   ├── home/  standings/  power/  matchups/  rivalries/
│   │   ├── records/  players/  stats/  teams/  draft/  search/
│   │   ├── about/              # coverage / attribution
│   │   └── placeholder/        # stub for not-yet-built views (managers index + profile)
│   │
│   ├── lib/
│   │   ├── api/                 # client.ts (openapi-fetch) + GENERATED schema.d.ts
│   │   ├── queryKeys.ts         # TanStack Query key factory
│   │   ├── format.ts            # numbers, records (W-L-T), dates — display only
│   │   └── rankflow.ts          # rank/bump-chart data shaping (display only)
│   │
│   ├── styles/                  # global.css imports tokens.css (the theme source of truth)
│   └── test/                    # render.tsx + setup.ts; component/feature tests are colocated
└──                              #   as *.test.tsx beside the code they cover (not a tests/ dir)
```

> **Manager pages are not built yet.** `features/placeholder/` backs the `managers` and
> `managers/:ownerId` routes as stubs; the owner analytics + `/v1/owners/*` endpoints exist
> and are tested, but the SPA views haven't been composed. Tracked in `10_OPEN_QUESTIONS.md`.

## Stack decisions (and why)

| Concern | Choice | Why |
|--------|--------|-----|
| BFF language/runtime | Python 3.11+, FastAPI, uvicorn | Reuse Phase 1 repository + tooling; same team-of-one mental model |
| BFF data access | `import ff_pipeline.repository` | The sanctioned DB boundary already exists and is typed/tested |
| BFF caching | in-process dict keyed by `pipeline_run_id` | Single user; rollups are stable between pipeline runs; trivial invalidation |
| Frontend framework | React 18 + TypeScript | Largest ecosystem for data UIs; durable; great charting options |
| Build tool | Vite | Fast dev server, simple, the modern default |
| Styling | Tailwind CSS + CSS variables | Token-driven theming; fast iteration; re-skinnable |
| Component layer | hand-built primitives (optionally shadcn/ui as a starting point) | Own the components so polish is additive; avoid a heavy dependency you can't restyle |
| Server state | TanStack Query | Caching, dedupe, background refresh; removes hand-rolled fetch logic |
| Routing | React Router (data router) | Deep-linkable views, loaders, nested layouts |
| Charts | Recharts | Declarative, React-native, covers line/bar/stacked/heatmap needs; swap to visx later if a chart outgrows it |
| API client | openapi-typescript (types) + a thin typed fetch wrapper | Contract-as-source-of-truth; build-time drift detection |
| Frontend tests | Vitest + React Testing Library + Playwright | Component + e2e parity with Python's pytest discipline |

All of these are open to revision — they're collected in `10_OPEN_QUESTIONS.md` (Q2).

## Data-flow walkthrough — loading the rivalry matrix

1. User opens `/owners/rivalries`. React Router renders the Rivalry feature page.
2. A TanStack Query hook calls `GET /v1/owners/rivalry-matrix` via the generated client.
3. The BFF route handler opens a repository session, calls
   `analytics.head_to_head.rivalry_matrix(session, league_id)`.
4. That function checks `cache.py`: keyed by `(latest_pipeline_run_id, "rivalry_matrix")`.
   On a hit, it returns instantly; on a miss it runs the SQL rollup over all matchups joined
   to teams→owners, computes per-pair W-L-T and margins, stores the result, and returns it.
5. The route wraps the result in the standard `{data, meta}` envelope (meta carries the
   pipeline run id and data freshness) and returns JSON.
6. The frontend renders a `Heatmap` from `charts/`. No computation happens in the browser.
7. TanStack Query caches the response; navigating away and back is instant; a new pipeline
   run (new run id) naturally busts both the server cache key and the client query.

## Failure modes and how each is handled

| Failure | Detection | Response |
|--------|-----------|----------|
| Database missing / Phase 1 never ran | repository session error / empty `pipeline_runs` | BFF returns `503 service_unavailable`; frontend shows a "run Phase 1 first" screen |
| Metric needs data Phase 1 lacks (e.g. 2010–2015 scoring) | analytics function detects no scored rows | Endpoint returns an explicit `available: false` marker, not zeros; UI renders a `DataGap` affordance |
| DST/team-defense points absent | scored breakdown missing for DEF slot | Box score marks those slots "not scored (known gap)"; team totals annotate the caveat |
| Stale frontend types after a schema change | `openapi-typescript` regen + `tsc` | Build fails until call sites are fixed — drift cannot ship |
| Slow first rollup | cache miss | First call computes & caches; subsequent calls are warm; loading skeletons cover the gap |
| BFF down | fetch error in client | TanStack Query error boundary → `ErrorState` with retry |

## What Phase 2 must NOT do (boundary guards)

- Never `INSERT/UPDATE/DELETE` against the database. The BFF opens read-only sessions and
  contains no upsert/write imports.
- Never import Phase 1 crawler/normalizer/scoring internals. Only `ff_pipeline.repository`
  (and, if needed, `ff_pipeline.scoring.rules`/`engine` as *pure* helpers for display, e.g.
  re-deriving a breakdown label — read-only, no I/O).
- Never embed the NFL cookie or any secret.
- Never put a derived-metric formula in the frontend.
