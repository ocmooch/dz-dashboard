# 00 — The Seam (orientation: read this first)

How **dz-dashboard** (Phase 2) and **danger-zone** / `ff_pipeline` (Phase 1) fit together. The
numbered docs (`01_SPEC` … `10_OPEN_QUESTIONS`) go deep on each domain; this one is the map
that ties them together so a new reader — or a returning one — knows what talks to what before
diving in.

## Repo boundaries (who owns what)

- **`../danger-zone` (Phase 1, package `ff_pipeline`)** — *owns and produces the
  data*. Crawlers (nflverse / Sleeper / nfl.com) → normalizer → scoring engine (dz-rules) →
  `reconstruct` / `backfill` → writes **`data/fantasy.db`** (a ~280 MB SQLite file) and one
  `pipeline_runs` row per run ("run #N"). It exposes its own read API too. **It is the only
  thing that writes.** The active dashboard source is the editable sibling checkout, so it tracks
  the current pipeline and live DB schema (including the ≥1.2.0 avatar columns).
- **`dz-dashboard` (Phase 2)** — *read-only consumer*, in two halves:
  - **BFF** — `src/ff_dashboard/` (FastAPI). Computes derived metrics, serves `/v1/*`.
  - **SPA** — `web/` (Vite + React + TS). Pure presentation; holds no business logic.

  It never writes the DB, never calls NFL.com / Sleeper, and never runs the pipeline.

## The seam is really two contracts

### 1. Python reuse seam (BFF ⇄ `ff_pipeline`)

`dz-dashboard` depends on `ff-pipeline` as an **editable path dependency** (`../danger-zone`)
in `pyproject.toml` `[tool.uv.sources]`; the reproducible / CI fallback is a pinned git tag
example (`v1.2.0` in the current snippet), but any pinned release must match the live DB schema
the dashboard reads. The live DB now requires the ≥1.2.0 schema with team/owner avatar columns.
`ff_pipeline` ships no `py.typed`, so the dashboard sets `follow_untyped_imports` for
`ff_pipeline.*` — we consume its real types without editing Phase 1. The BFF imports a deliberately
small surface:

- `repository.models` — the ORM tables (`leagues, seasons, owners, teams, scoring_rules,
  players, team_rosters, player_availability, matchups, transactions, player_stats_raw,
  player_stats_scored, projections, pipeline_runs, source_health`).
- `repository.queries` — readers such as `get_season`, `list_seasons_for_league`, `get_owner`,
  `get_team`, `get_player`, `search_players`, `latest_pipeline_run`, `top_scorers`,
  `season_totals`, `owner_career_aggregates`.
- `api._meta.build_meta(session)` → the `{last_updated, source, pipeline_run_id}` block from
  the latest run.
- `api.errors` — `install_error_handlers`, `not_found` (404), `bad_request` (400),
  `service_unavailable` (503).
- `api.schemas` — `Envelope, Meta, ErrorBody, HealthResponse, PlayerLite, PlayerOut,
  SeasonTotal, TopScorer`, reused **verbatim** so the contract shape matches Phase 1's read
  API. The dashboard's own `api/schemas.py` is purely additive.

### 2. HTTP contract seam (SPA ⇄ BFF)

The SPA's **only** data path. The BFF serves `/v1/*` (additive over Phase 1) plus
`/openapi.json`. The SPA generates its typed client (`openapi-typescript` →
`web/src/lib/api/schema.d.ts`) via `npm run gen:api`; a drift check (regenerate, then a
non-empty `git diff` fails CI) makes contract drift impossible to merge. Every success
response is an `Envelope {data, meta}`. **Where a metric is unavailable for the requested
scope, the endpoint returns `200` with `{available: false, reason: "..."}` — never a `0`,
never a `404`.** This is how "honest about gaps" is enforced at the contract level.

## Data flow, end to end

```
sources → ff_pipeline ingest → scoring (dz-rules) → reconstruct
        → data/fantasy.db + pipeline_runs                 (Phase 1 writes)
        → BFF opens that same file read-only / WAL          (no copy → no drift)
        → analytics/ pure fns (Session → dict)
        → api/routes wrap in Envelope + build_meta
        → /openapi.json → generated TS client → TanStack Query → React pages
```

The read-only engine (`engine.create_readonly_engine`) points at the live file
(`../danger-zone/data/fantasy.db` by default, via `Settings.database_url`). `AnalyticsCache`
keys every rollup on `(latest_pipeline_run_id, name)`, so when Phase 1 runs again the run id
changes and the whole cache is bypassed — invalidation is free and correct.

## Gotchas (the things worth stating once)

- **Two rows per game.** Each `matchups` game is stored twice (one row per team's
  perspective); a bye is `opponent_team_id IS NULL`. Exclude byes and don't double-count
  pairwise head-to-head.
- **Owner identity spans seasons and renames.** Career and rivalry math keys on `owner_id`,
  not `team_id` (teams are per-season).
- **Per-player fantasy scoring spans 2010–2025.** `player_stats_scored` covers the completed
  historical window since the pre-2016 reconstruction landed (F-51). The only unscored season is
  normally the current/in-progress one. Gap affordances are data-driven on the per-season
  `is_scored` flag — never a hardcoded year. Coverage flags ride on `/v1/meta`:
  `seasons_present`, `seasons_scored`, `reconstruction_complete`,
  `availability_current_season_only` (true), `dst_scoring_complete` (now data-derived — true once
  every scored season has scored DEF rows).
- **Standings rank.** Prefer Phase 1's reconstructed `final_rank` (the NFL.com truth) for full
  seasons; otherwise compute wins-desc → points-for-desc, exposing `rank_basis` and a
  `tiebreak_caveat` flag (true when computed *and* season < 2019). Do not re-implement the
  league's old best-of-3 tiebreak. See `04_ANALYTICS_MODEL.md`.
- **Never hardcode week counts** (14 / 17) — use `analytics/common.regular_season_weeks`
  (falls back to the max played week).
- **Strictly read-only / WAL** against a large live DB. No migrations, no writes from the
  dashboard.

## Where things run

| Piece | Command | Address |
|-------|---------|---------|
| BFF | `dz-dashboard serve` (`ff_dashboard.server:main`) | `127.0.0.1:8800` (`DASHBOARD_HOST` / `DASHBOARD_PORT`) |
| SPA (dev) | `npm run dev` (Vite) | `127.0.0.1:5173`, proxies `/v1`, `/health`, `/openapi.json` → 8800 |

`create_app(engine=…)` is injectable so integration tests bind a temp-file SQLite engine. In
dev the Vite proxy means the browser only ever talks to one origin (no CORS); the BFF also
allows the `5173` origin directly. Tests: backend uses a hand-authored fixture DB in
`tests/conftest.py` with documented known answers; the frontend uses Vitest (with MSW +
Playwright for the feature/e2e layers).

---

> **The discipline, restated:** all derived-metric math lives in `ff_dashboard/analytics/`
> (pure, unit-tested); the SPA only renders numbers the BFF already computed; the client is
> generated, never hand-edited; gaps are shown honestly, never faked.
