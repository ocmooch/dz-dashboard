# 03 — Data Access & Data Reliability Map

This is the most consequential Phase 2 document, the counterpart to Phase 1's
`03_DATA_SOURCES.md`. Phase 2 has exactly **one** data source — the Phase 1 SQLite
database — but it must understand *precisely* what in that database is trustworthy, what is
partial, and what is absent, so the dashboard never lies by omission.

## How Phase 2 reads Phase 1

**Decision (for sign-off, see `10_OPEN_QUESTIONS.md` Q1): the BFF reuses
`ff_pipeline.repository` and reads the SQLite file directly, read-only, in-process.**

Concretely:

- `ff_dashboard.api.deps` builds a SQLAlchemy `Session` from the same `DATABASE_URL`
  Phase 1 uses, via `ff_pipeline.repository.database`. The session is used read-only.
- Simple reads reuse Phase 1's existing functions in `ff_pipeline.repository.queries`
  (e.g. `get_league`, `list_seasons_for_league`, `standings_for_season`, `search_players`,
  `player_scored_stats`).
- New, heavier rollups live in `ff_dashboard.analytics.*` and may add **read-only** query
  helpers to `ff_pipeline.repository.queries` when a query is genuinely reusable. Anything
  Phase-2-specific stays in `ff_dashboard`.

Why not go through the Phase 1 HTTP API? Because the analytics rollups need set-based SQL
over the whole history; pulling that through a paginated read API (max 500 rows/call) would
be slow and chatty. Direct repository reuse keeps aggregation in SQL where it belongs while
preserving the "repository is the only thing that touches the DB" rule.

> **SQLite concurrency note.** Phase 1's pipeline takes a file lock and is the only writer.
> The BFF is a reader. Open the engine with WAL mode and a read-only/`busy_timeout` pragma
> so a dashboard read never collides with a running sync. This is a one-line engine option;
> document it in operations.

## The tables Phase 2 reads (from Phase 1's `04_DATA_MODEL.md`, as built)

Confirmed present in `ff_pipeline.repository.models`:

`leagues`, `seasons`, `owners`, `teams`, `scoring_rules`, `players`,
`player_id_overrides`, `team_rosters`, `player_availability`, `matchups`,
`transactions`, `player_stats_raw`, `player_stats_scored`, `projections`,
`trending_players`, `pipeline_runs`, `source_health`.

Phase 2 reads all of these except the operational ones (`source_health`,
`player_id_overrides`) which it uses only for provenance/health display.

## Reliability map — READ THIS BEFORE DESIGNING ANY VIEW

Drawn from Phase 1's `PHASE1_COMPLETION_PLAN.md` audit and decisions. Each row tells you
whether a metric built on it is **solid**, **partial**, or **absent**, and what the UI must
do.

| Data | Coverage | Reliability | UI obligation |
|------|----------|-------------|---------------|
| nflverse raw weekly stats (`player_stats_raw`) | 2010–2025, all 16 seasons (17–19k rows/season) | **Solid** | Use freely |
| Scored fantasy points (`player_stats_scored`) | **2016–2025 only** (~182k rows) | **Solid 2016+** | 2010–2015 show "unscored" — never 0 points |
| Scoring rules (`scoring_rules`) | 2016–2025 (51 rules/season, current ruleset propagated) | **Solid 2016+; assumed-stable** | Note in scoring-rules view that 2016+ uses one ruleset; pre-2016 unknown |
| Player identity & cross-IDs (`players`) | 25,035 GSIS / 3,525 Sleeper resolved | **Solid** | Use freely; some obscure players lack IDs (0-point edge cases) |
| Transactions (`transactions`) | per-season log, real | **Solid** | Use freely |
| Standings / season metadata (`seasons`, `teams`: champion, final_rank, W-L-T, PF/PA) | reconstructed 2010–2025 | **Solid after the reconstruction run completes** (see note) | If a season lacks champion/records, show "season metadata pending" |
| Per-week lineups (`team_rosters`: starters, points, locked) | reconstructed from gamecenter, 2010–2025 | **Solid after reconstruction**; pre-2016 lineups exist but carry no scored points | Pre-2016 box scores show lineup + NFL.com points if captured, but no league-scored breakdown |
| Full-season matchups (`matchups`) | all weeks, reconstructed | **Solid after reconstruction** | Use freely; playoff vs consolation bracket is **not** distinguished (see below) |
| Player availability (`player_availability`: FA / owned / waivers) | **current season only** | **Absent for history** | Availability views are current-season-only; historical availability renders "not reconstructable" |
| Team-defense / DST scoring | incomplete (no nflverse team-defense rollups) | **Partial** | DST lineup slots marked "not scored (known gap)"; team totals annotate it |
| Projections (`projections`, Sleeper) | current season forward | **Partial/seasonal** | Projection-vs-actual only where projections exist |
| Trending players (`trending_players`, Sleeper) | current, rolling | **Partial** | Optional "buzz" widget, current season only |

### Important reconstruction caveat (timing)

At the time this package was written, Phase 1's **historical reconstruction code is complete
and tested but the full 16-season run was pending** (`PHASE1_COMPLETION_PLAN.md` item C5,
~2 hrs of live scraping). Phase 2 assumes that run has completed before the relevant views
are built. **Prerequisite:** confirm `ff-pipeline reconstruct --start 2010 --end 2025` has
run and `verify --sweep` meets the Phase 1 bar before building standings/matchup/box-score
views. Build order in `09_ROADMAP.md` front-loads the views that depend only on
already-solid data (players, stats, owners career from records) so work can start even if
reconstruction is still finishing.

### Specific gotchas the analytics layer must encode (not the frontend)

- **Playoff vs consolation indistinguishable in history.** `matchups.is_playoff` is derived
  from a week boundary; `is_consolation` and `made_playoffs` may be unset for historical
  seasons. The bracket view must treat "playoff week" as "post-regular-season week," not as a
  proven championship bracket, and say so.
- **Regular-season week count varies by season** (14 vs 17). Never hardcode 14 or 17; read
  `seasons.regular_season_weeks`.
- **`season_type`** in `player_stats_raw` is `REG`/`POST`/`PRE` — filter to `REG` for
  regular-season aggregates unless a view explicitly wants playoffs.
- **Owner identity is persistent; team identity is per-season.** Career/rivalry metrics key
  on `owner_id`, joining through `teams.owner_id`. Team names change across seasons.
- **Two matchup rows per game.** `matchups` has one row per (season, week, team). A
  head-to-head game is two rows; dedupe by pairing `team_id`/`opponent_team_id` when counting
  games so you don't double-count.

## Provenance

Every BFF response carries the Phase 1 `meta` envelope (`last_updated`, `source`,
`pipeline_run_id`) sourced from `latest_pipeline_run`. The dashboard shows a small "data as
of …" indicator in the app shell so the user always knows how fresh the picture is and which
pipeline run produced it.

## What Phase 2 explicitly does NOT read or do

- Does not read crawler caches, raw HTML fixtures, or `.env`.
- Does not call NFL.com, nflverse, or Sleeper directly — all third-party data arrives only
  via Phase 1's tables.
- Does not write, ever.
