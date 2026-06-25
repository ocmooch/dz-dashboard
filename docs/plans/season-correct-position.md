# Plan — Season-correct player position

**Problem.** Box scores render a single static `players.position` (the player's
latest/canonical position). NFL position is season-dependent, so any player who
changed positions — or was ever mislabeled — is shown wrong for the seasons that
disagree. Surfaced by: *"Harry's 2014 playoff team shows Jordan Matthews playing
TE in the WR slot."* JM's stored position is `TE`; he was a `WR` every season he
was rostered (2014–2018).

This is the exact shape of the already-shipped season-correct **NFL team** fix
(F-54, `queries.player_season_teams`). We mirror it for position.

## Audit (identify) — authoritative source = nflverse per-season **rosters**

`nflreadpy.load_rosters(seasons)` keyed by `gsis_id` gives the season-correct
position. (The all-time `load_players()` table is season-blind — it lists JM's
gsis as `TE/DEV` today, so a naive "fix the row" check *misses* him. Only rosters
are authoritative.)

Cross-checking stored `players.position` vs per-season roster position across
2010–2025 (4,399 rostered player-seasons) found **10 players**:

| Class | Players |
|-------|---------|
| Plain-wrong (every season) | Jordan Matthews (TE→WR), N'Keal Harry (TE→WR) |
| Season-dependent (career conversion) | Cordarrelle Patterson (WR→RB), Ty Montgomery (WR→RB), Terrelle Pryor (QB→WR), Dexter McCluster, Danny Woodhead |
| Fantasy/edge quirks | Taysom Hill (TE-eligible / NFL QB), Travis Hunter (CB/WR), Cameron Dicker (K/P) |

Position folding for the check: `HB`,`FB` → `RB`.

## Design

### danger-zone (Phase 1) — owns the data
1. **New table `player_season_positions`** — `(player_id, season_year, position,
   source, created_at, updated_at)`, unique on `(player_id, season_year)`. Alembic
   migration. Mirrors how per-season `nfl_team` lives on stored data.
   - *Why a table, not a column on `player_stats_raw`:* rosters cover bench/DNP
     players who have no weekly stat row (≈237 rostered player-seasons lack a
     primary stat row); rosters is the more complete source.
2. **Ingest** in `crawlers/nflverse/runner.py` (`run_nflverse`): load
   `client.rosters(seasons)`, resolve `gsis_id → player_id` (reuse
   `_gsis_id_to_player_id`), upsert one row per (player, season) with the season's
   roster position (mode of weekly position; tie → latest week). Add a
   `client.rosters()` wrapper if not already exposed.
3. **Repository query** `player_season_positions(session, player_ids, season_year)
   -> dict[int,str]` in `repository/queries.py`, mirroring `player_season_teams`
   (batched, fold `HB`/`FB`→`RB`). Plus single-player wrapper `player_position()`.
   Absent player-season → caller falls back to static `players.position`.
4. **Integrity validator (catch)** — sibling to `player_identity_integrity.py`:
   re-runs the rosters cross-check, returns divergences as a data-quality finding
   the dashboard coverage panel can surface. Add to the integrity CLI / CI.
5. **Merge tightening (prevent recurrence at the source)** — in
   `normalizer/player_ids.py::_merge_into`, allow a higher-precedence nflverse
   position to correct an *unrecorded* incumbent (today the conservative rule lets
   a wrong incumbent stick). Narrow: position dimension only, nflverse source only.
6. **Backfill script** — populate `player_season_positions` for 2010–2025 from
   rosters. Validate on a DB **copy** (full diff) before applying to the live DB,
   per project norm ("green gate ≠ real DB works").

### dz-dashboard (Phase 2) — presentation only
7. Box-score builder (`analytics/matchups.py:897`, the `"position": player.position`
   emit) routes through a season-scoped position resolved from the new query,
   falling back to `player.position`. Batched per page like the nfl_team path.
   No new math — pure data substitution. No API-shape change (same `position`
   field), so no gen:api drift.

## Files to touch
- danger-zone: `repository/models.py` (+ Alembic version), `repository/queries.py`,
  `crawlers/nflverse/runner.py`, `crawlers/nflverse/client.py` (rosters wrapper),
  `repository/player_position_integrity.py` (new), `scripts/backfill_season_positions.py`
  (new), tests.
- dz-dashboard: `analytics/matchups.py`, its test.

## Done when
- JM reads **WR** in 2014–2018 box scores; Patterson reads **WR** in 2014 and
  **RB** in 2021; all 10 audit players render their season-true position.
- Validator runs clean (0 unexplained divergences) and is wired into CI.
- Backfill applied to live DB after copy-validation; static fallback intact for
  player-seasons with no roster row.
- Green gate both repos; box-score click-through on Harry's 2014 playoff team.

## Branches
- danger-zone: `feature/season-correct-position` (from dev)
- dz-dashboard: `feature/season-correct-position` (from dev)
