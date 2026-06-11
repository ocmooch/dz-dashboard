# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Phase 2 analytics dashboard for the Danger Zone fantasy football league. It has two pieces and a hard contract between them:

1. **`ff_dashboard`** — a read-only Python/FastAPI backend-for-frontend (BFF). All derived-metric math lives here. Lives in `src/ff_dashboard/`.
2. **`web/`** — a React + TypeScript SPA. Pure presentation. Holds no business logic — every number comes from the BFF.

The BFF depends on the Phase 1 sibling package `ff-pipeline` (checkout at `../danger-zone`), reusing its SQLAlchemy models and repository queries to read `../danger-zone/data/fantasy.db` read-only. The database is never written by this package.

## Commands

### Backend (run from repo root)

```bash
uv sync --extra dev          # install deps (first time or after pyproject.toml change)
uv run dz-dashboard info     # show resolved config
uv run dz-dashboard serve    # API on http://127.0.0.1:8800
uv run dz-dashboard serve --reload   # dev: auto-reload on code changes

uv run pytest                # all tests
uv run pytest tests/test_p2_analytics_unit.py   # single file
uv run pytest -k "test_standings"               # single test by name

uv run ruff check            # lint
uv run ruff format           # format
uv run mypy src/             # type check (strict)
```

All four (pytest, ruff check, ruff format, mypy) must pass before committing.

### Frontend (run from `web/`)

```bash
npm install                  # first time only
npm run dev                  # SPA on http://127.0.0.1:5173
npm run typecheck            # tsc --noEmit
npm run build                # full build (typecheck + vite)
npm run test                 # vitest (unit)
npm run gen:api              # regenerate src/lib/api/schema.d.ts from live BFF at :8800
npm run gen:api:check        # diff schema.d.ts vs live BFF (CI check)
```

To see the app, both processes must run: the BFF on `:8800` and the Vite dev server on `:5173`. Vite proxies `/v1`, `/health`, and `/openapi.json` to the BFF.

## Architecture

```
Phase 1 SQLite (../danger-zone/data/fantasy.db)
        │ read-only, in-process via ff_pipeline.repository
        ▼
src/ff_dashboard/
  settings.py          # pydantic-settings: DB path, host/port, cache TTL, CORS
  engine.py            # create_readonly_engine() — opens SQLite with WAL + query_only
  cache.py             # AnalyticsCache: process-local dict keyed by (pipeline_run_id, name)
  server.py            # typer CLI: `serve` + `info` commands
  analytics/           # PURE functions: Session → metrics. No FastAPI imports here.
    common.py          # require_league(), regular_season_weeks(), owner/team name maps
    standings.py       # standings, week-by-week, streaks
    power.py           # power ranking model
    matchups.py        # box-score enrichment, optimal lineup, bench points
    head_to_head.py    # all-time owner-vs-owner records, rivalry matrix
    records.py         # records book / hall of fame rollups
    teams.py / owners.py / draft.py / players.py / search.py / coverage.py
  api/
    main.py            # FastAPI app factory — engine and cache stored on app.state
    deps.py            # SessionDep, CacheDep (pulled from app.state, not module globals)
    schemas.py         # Pydantic response models for all analytics shapes
    routes/            # One file per domain: seasons, matchups, players, power, draft, records
        
web/src/
  app/                 # router, layout shell, QueryClient + Router providers
  design-system/       # Button, Card, Stat, Badge, Table, Tabs, DataGap, Skeleton, etc.
  charts/              # Recharts wrappers (LineTrend, BarCompare, Heatmap, StackedBreakdown)
  features/            # pages = composition only; no math, no direct fetch
  lib/
    api/               # GENERATED typed client (schema.d.ts + thin openapi-fetch wrapper)
    queryKeys.ts       # TanStack Query key factory
    format.ts          # display-only: numbers, W-L-T records, dates
```

## Key patterns

**Analytics layer:** Every analytics module exports pure functions taking `Session` (and optionally `AnalyticsCache`) and returning plain Python objects. Route handlers call `cache.get_or_compute(session, "name", lambda: analytics_fn(session))`. Cache invalidates automatically when the pipeline run id changes.

**SessionDep / CacheDep:** Routes get their session and cache from FastAPI DI via `deps.py`. Both live on `app.state` (not module-level singletons), so tests can bind a temp-file engine and fresh cache without monkey-patching.

**Test fixtures:** `tests/conftest.py` builds a hand-authored SQLite fixture ("Danger Zone Test League", 2015–2017) with known-answer constants in `KNOWN`. The fixture deliberately encodes every data-gap case: an unscored 2015 season, a DST starter with no scored rows, current-season-only availability. Unit tests assert against `KNOWN` values to the decimal; endpoint tests (`test_p*_endpoints.py`) use the `client` fixture.

**API contract:** `web/src/lib/api/schema.d.ts` is generated from the live BFF's `/openapi.json`. Never hand-edit it. After any BFF response shape change, run `npm run gen:api` from `web/` while the BFF is running. The TypeScript build flags every stale call site.

**Two matchup rows per game:** `matchups` has one row per team perspective. When counting games between two owners, always dedupe by pairing `team_id`/`opponent_team_id` to avoid double-counting.

**Owner vs team identity:** Career and rivalry metrics key on `owner_id`. Team names change per season. Join through `teams.owner_id`. Use `analytics/common.py:team_owner_map()`.

**Regular-season weeks:** Never hardcode 14 or 17. Always use `analytics/common.py:regular_season_weeks(session, season)`, which reads `seasons.regular_season_weeks` and falls back to `max(matchup.week)`.

**Data gaps (non-negotiable):** Scored fantasy points only exist 2016+. Player availability only exists for the current season. DST scoring is incomplete. These must be surfaced as `available: false` or explicit gap markers — never faked as zeros. The `DataGap` component on the frontend renders these affordances.

## Non-negotiable boundaries

- No `INSERT/UPDATE/DELETE`. The BFF opens read-only sessions (`create_readonly_engine` in `engine.py`).
- Only import `ff_pipeline.repository` (models + queries). Never import Phase 1 crawler, normalizer, or scoring write code.
- All derived-metric formulas stay in `ff_dashboard/analytics/`. Never compute metrics in `web/`.
- The frontend's typed client must be regenerated (never hand-edited) after BFF schema changes.

## Environment

Copy `.env.example` to `.env` if `../danger-zone/data/fantasy.db` is not at the default location. The dashboard has no secrets. The BFF binds to `:8800`; the Vite dev server expects this and proxies to it.
