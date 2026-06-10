# Handoff → danger-zone (ff-pipeline): season-correct player NFL team (F-54)

**Repo:** `/home/mainuser/danger-zone`  ·  **DB:** `data/fantasy.db` (SQLite)
**Dashboard branch that surfaced it:** `feature/season-correct-nfl-team` (dz-dashboard).

## The gap

The dashboard renders a player's **NFL team** (e.g. "KC", "BUF") on **season-scoped**
surfaces — historical stats leaderboards and historical team rosters — but the only value
it can read, `players.nfl_team`, is a single **current** snapshot. So a 2015 leaderboard
shows players' *2026* NFL teams. This is the NFL-team analog of the fantasy-name problem
that PRs #47/#49/#50 fixed for `teams.team_name` — except that one had a real per-season
source (`historical_team_names`, keyed by the NFL.com slot) and **this one does not**.

The dashboard is read-only and cannot fix this; it can only render the current value or a
gap affordance. This handoff asks you to persist the per-season team so the dashboard can
render the season-correct value behind the existing read boundary.

### Confirmed: no per-season NFL team exists in the DB today

A read-only audit of `data/fantasy.db` found **no per-season player→NFL-team column
anywhere**:

| Table | Team columns | Per-season player NFL team? |
|-------|--------------|-----------------------------|
| `players` | `nfl_team` | No — single current value (see below) |
| `player_stats_scored` | — | No — only `total_points` + `points_breakdown` JSON |
| `team_rosters` | `team_id` (fantasy team) | No — `extra_data` JSON carries `opponent` (e.g. `@BUF`) + `game_status`, i.e. the **opponent**, not the player's own team |
| `player_availability` | `owning_team_id` (fantasy team) | No |

`players.nfl_team` is populated from nflverse's **current** team:
`crawlers/nflverse/client.py:272 nfl_team=_opt_str(row.get("latest_team"))` (the player-
metadata path, `players()` → `_upsert_players`). It is by construction "latest team," not
"team that season." (This is the same stale-`nfl_team` concern raised as D3 in
`players-audit-danger-zone.md`.)

### The good news: the per-season team is already loaded, just not persisted

nflverse already ships the per-season-week NFL team, and the pipeline already reads it:
`crawlers/nflverse/client.py:210 nfl_team=_opt_str(row.get("team"))` inside
`player_stats(seasons)`. That builds `NflversePlayerStat(gsis_id, season_year, week,
nfl_team, nfl_opponent, …)` — the **same object that feeds `player_stats_scored`**. The
per-week `team` (and `nfl_opponent`) are dropped before persistence; only `total_points`
and `points_breakdown` land in the table. So this is a *persist-an-already-loaded-field*
task, not a new ingestion source.

You also already have **season-correct franchise resolution** for one purpose:
`crawlers/nflverse/franchises.py:resolve_def_team_abbrev(player, season_year)` handles
relocations (OAK→LV, SD→LAC, STL→LAR, "Washington Football Team"→WAS). Whatever you
persist should likewise carry the abbreviation nflverse used **for that season**, not the
relocated/current one.

## What to do upstream

Persist the per-season (ideally per-week, else per-season) NFL team for each player, keyed
so the dashboard can look it up by `(player_id, season_year)`. Two shapes, pick one:

- **(a) Per-week column on `player_stats_scored`** — add `nfl_team VARCHAR` (and optionally
  `nfl_opponent`) and populate it from `NflversePlayerStat.nfl_team` at the same point
  `total_points` is written. Most faithful (handles mid-season trades); the dashboard would
  read the modal/most-recent team for a season, or the exact week on box scores.
- **(b) Derived per-season mapping** — a small `player_season_team (player_id, season_year,
  nfl_team)` table (or a materialized helper), one row per player-season, taken as the
  team of record for that fantasy season. Simpler for the dashboard; loses mid-season
  trade detail.

Either way the value must be the **season-correct** abbreviation (apply the
`franchises.py` relocation logic, or store nflverse's raw per-season `team` which is
already correct for the year).

## One coordinated read-API addition

The dashboard reads only `ff_pipeline.repository`. To consume this it needs **one** of:

- a read-only repository helper, e.g. `player_nfl_team(session, player_id, season_year)` →
  `str | None`, or a season-team map for a batch of players (the stats leaderboard fetches
  many players at once — prefer a batch helper to avoid N+1), **or**
- the per-week column from (a) exposed on whatever scored-row repository read the dashboard
  already uses, so it can group by season.

This is additive. When it lands, the dashboard will: in `analytics/stats.py:season_totals`
and `analytics/teams.py:team_season_roster`, replace the `Player.nfl_team` read with the
season-correct lookup, falling back to the stored current value (and/or a gap affordance)
when the season/player is unknown — exactly mirroring how `period_team_name()` falls back
to the stored fantasy name. No `/openapi.json` response **shape** change is required (the
`nfl_team` field already exists on `PlayerScored` / roster rows); only the *value* becomes
season-correct. Coordinate so the dashboard `gen:api` drift check runs in the same cycle if
any schema field is added.

## Done when

- A per-season (or per-week) season-correct `nfl_team` is persisted for every player-season
  nflverse covers; players/seasons nflverse cannot identify stay NULL (an honest gap, not a
  guess).
- The dashboard can read it through `ff_pipeline.repository` (helper or column) without
  doing its own joins or franchise math.
- Spot check: a 2015 stats leaderboard / 2015 team roster shows 2015-era NFL teams (e.g. a
  player who has since changed teams shows the 2015 team), and relocated franchises render
  with the season-correct code (a 2015 Raider reads "OAK", not "LV").

## Dashboard-side follow-up (after this lands)

Retire F-54 on the dashboard by routing the season-scoped `nfl_team` reads through the new
lookup with a stored-value fallback. Until then the dashboard continues to show the current
`players.nfl_team` — see the F-54 entry in `docs/ACTIVE_WORK.md` for the holding decision.
