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
| Scored fantasy points (`player_stats_scored`) | **2010–2025** since the pre-2016 reconstruction landed (F-51) | **Solid** for every completed season | A season without scoring (now normally the current/in-progress one) shows "unscored" — never 0 points. Gate on `is_scored`, never a hardcoded year |
| Scoring rules (`scoring_rules`) | 2016–2025 (51 rules/season, current ruleset propagated) | **Solid 2016+; assumed-stable** | Note in scoring-rules view that 2016+ uses one ruleset; pre-2016 unknown |
| Player identity & cross-IDs (`players`) | 25,035 GSIS / 3,525 Sleeper resolved | **Solid** | Use freely; some obscure players lack IDs (0-point edge cases) |
| Transactions (`transactions`) | per-season log, real; dated add/drop/waiver/trade/draft/lineup rows | **Solid**; no FAAB bid rows found in the current DB spot check | Use freely; render FAAB as nullable/missing, never as 0 |
| Standings / season metadata (`seasons`, `teams`: champion, final_rank, W-L-T, PF/PA) | reconstructed 2010–2025 | **Solid after the reconstruction run completes** (see note) | If a season lacks champion/records, show "season metadata pending" |
| Per-week lineups (`team_rosters`: starters, points, locked) | reconstructed from gamecenter, 2010–2025 | **Solid after reconstruction**; lineups exist for the historical window | Box scores show lineup + league-scored breakdown wherever the season is `is_scored:true`; a genuinely missing row renders a gap |
| Full-season matchups (`matchups`) | all weeks, reconstructed | **Solid after reconstruction** | Use freely; playoff vs consolation bracket is **not** distinguished (see below) |
| Player availability (`player_availability`: FA / owned / waivers) | **current season only** | **Absent for history** | Availability views are current-season-only; historical availability renders "not reconstructable" |
| Team-defense / DST scoring | **2016–2025**, scored from nflverse team-defense rollups | **Solid 2016+** | DST starters carry real league points; a genuinely-missing team/week row still shows "not scored", never 0 |
| Projections (`projections`, Sleeper) | current season forward | **Partial/seasonal** | Projection-vs-actual only where projections exist |
| Trending players (`trending_players`, Sleeper) | current, rolling | **Partial** | Optional "buzz" widget, current season only |

`/v1/meta/coverage` is the runtime source of truth for the coverage envelope above. It exposes
the feed-by-season/week matrix, relevance/exclusion tallies, and diagnostic identity-split
candidates so views can render self-explaining gaps instead of bare absence. It also reports
strong NFL.com source-identity mismatches supplied by Phase 1; repairs remain upstream while the
dashboard exposes the read-only integrity state. The prose table is orientation; the matrix and
its contract tests are authoritative for current DB truth.

### Important reconstruction caveat (timing)

Phase 1's historical reconstruction has completed, and F-51 added pre-2016 per-player scoring.
If the DB is regenerated, confirm `ff-pipeline reconstruct --start 2010 --end 2025` plus the
post-regen verification sweep before trusting standings/matchup/box-score views. Build order in
`09_ROADMAP.md` still documents the original dependency sequencing.

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
- **Period-correct team names may differ from the stored `team_name`.** After owner-identity
  repair, some past team-season rows carry a current/canonical label rather than the name the
  manager actually used that year. For season-scoped surfaces (e.g. player ownership
  timelines), resolve the label through
  `analytics/historical_team_names.period_team_name(team, season_year)`, which overrides from
  a recovered `(season_year, team_abbrev) → name` table sourced from pre-merge NFL.com rows,
  falling back to the stored `team_name` when the slot/year is unknown.
- **Two matchup rows per game.** `matchups` has one row per (season, week, team). A
  head-to-head game is two rows; dedupe by pairing `team_id`/`opponent_team_id` when counting
  games so you don't double-count.
- **Roster snapshots are *week-end* state.** A `team_rosters` row set for `(team, week)` reflects
  the roster as it stood at the *end* of that week — not mid-week, and not during a playoff BYE.
  The default bench is 6 (so a typical roster is starters + 6, e.g. 9 + 6 = 15), but **bench size
  is variable**: a manager can carry more than 6 only by leaving a starting slot empty (K/DST is
  frequently dropped to juggle players across games), and can carry fewer by dropping without
  replacing. So a week's row count can be *under* or *over* the usual size. Consequences the
  analytics encodes (not the frontend): never assume a fixed roster size or a 6-cap on bench;
  render every stored bench/IR row (don't truncate); and pad a short week up to the team-season's
  usual size with empty/dashed slots (`team_roster` → `is_empty`, derived from the snapshots, not
  league settings) so a dropped-everyone week reads as open spots rather than a smaller roster.

### `is_scored` means *per-player fantasy scoring*, not "season complete" (F-16/F-35)

The season-level `is_scored` flag (true ⇔ the season has `player_stats_scored` rows) gates
exactly **one** layer: per-player fantasy points. Since the pre-2016 reconstruction landed
(F-51) every completed season 2010–2025 is `true`; the flag is now `false` only for a season
with no scoring yet — normally the current/in-progress one. Even when `false`, the
**team-level** data may still exist (team scores, margins, standings, final ranks, rosters,
drafts) for a completed season, though for a live season it is partial. Affordances must
therefore scope the gap to "per-player fantasy scoring not available for this season",
gate on `is_scored` (**never a hardcoded year**), and must **not** imply the grid/standings/roster
is incomplete for a completed season. The
gap-validation harness (`tests/test_coverage_integrity.py`, F-43) asserts this split
mechanically: present-but-unscored seasons still carry non-null team scores.

### DST: presence vs. value accuracy — a dev-facing fact (F-48)

`/v1/meta`'s `dst_scoring_complete` asserts **presence**: every scored season carries at least
one scored team-defense (DEF) row, so "DST is scored end-to-end" — and it is authoritative for
that. It does **not** certify per-stat *value accuracy*. A known upstream gap exists: nflverse
team-defense **yards/sacks read low**, so some DST point values are understated even though the
rows are present and scored (rooted in nflverse team-defense rollups, tracked in the
danger-zone players audit). This is a data-quality concern, **not** a presence hole, so it does
not flip `dst_scoring_complete` to `false`. Keep it a dev-facing note; do not surface it to
end-users as a coverage gap.

## Provenance

Every BFF response carries the Phase 1 `meta` envelope (`last_updated`, `source`,
`pipeline_run_id`) sourced from `latest_pipeline_run`. The dashboard shows a small "data as
of …" indicator in the app shell so the user always knows how fresh the picture is and which
pipeline run produced it.

## Avatars: an on-disk asset store, read-only (Q11)

Team logos are the one binary the BFF serves. Phase 1 stores avatar **bytes on disk**, not in
SQLite: `teams.team_avatar_asset_id` → `assets.storage_path` is a content-addressed relative
path (e.g. `aa/aa…png`); the row holds only metadata (`sha256`, `content_type`, `byte_size`).
The store root is the `ASSETS_ROOT` setting, defaulting to `<db_dir>/assets` (Phase 1's layout).
`GET /v1/teams/{team_id}/avatar` resolves the path under that root, guards against escaping it,
and streams the file — still read-only, still no third-party calls. A missing file 404s so the
UI falls back to a monogram.

**Owner/manager photos are a true source gap.** `owner_avatar_asset_id` is populated on 0 rows,
so no owner avatar is exposed; manager chips stay monograms until an upstream backfill lands
(relate F-06). Team logos are populated on ~190 per-season rows.

## What Phase 2 explicitly does NOT read or do

- Does not read crawler caches, raw HTML fixtures, or `.env`.
- Does not call NFL.com, nflverse, or Sleeper directly — all third-party data arrives only
  via Phase 1's tables.
- Does not write, ever.
