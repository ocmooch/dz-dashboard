# Handoff → danger-zone (ff-pipeline): players data audit

**Repo:** `/home/mainuser/danger-zone`  ·  **DB:** `data/fantasy.db` (SQLite)
**Context:** The dz-dashboard `/players/` view exposed systemic data-quality problems
that originate in Phase 1 ingestion/normalization. The dashboard is read-only and cannot
fix these — it can only label gaps. This handoff asks you to fix the source so the
dashboard can render real values instead of gap affordances.

Do **not** change the read API's response *shapes* except the one additive field called
out below; the dashboard is generated off `/openapi.json` and any shape change there must
be coordinated. Everything else here is data-population / correctness work behind the
existing columns.

## Findings (measured against `data/fantasy.db`, 3093 players)

| # | Problem | Evidence | Where it lives |
|---|---------|----------|----------------|
| D1 | **`last_season` is NULL for 100% of players** (all 3093) | `SELECT COUNT(*) FROM players WHERE last_season IS NULL;` → 3093 | nflverse player-metadata population / upsert |
| D2 | **`rookie_year` NULL for 322 players** (88 of them league-rostered) | `... WHERE rookie_year IS NULL` → 322; rostered subset → 88 | nflverse player metadata |
| D3 | **`is_active` is unreliable** — retired players flagged active with a "current" `nfl_team` | A.J. Feeley (QB, last NFL 2011) → `is_active=1`, `nfl_team='LA'`; 478 *league-rostered* players have `is_active=1` but no roster row since before 2024 | `is_active` semantics + stale `nfl_team` |
| D4 | **879 "ghost" players** never rostered and never scored, sitting in the index | never in `team_rosters` AND never in `player_stats_scored` → 879 (450 flagged `is_active=1`) | over-broad ingestion scope / stubs |
| D5 | **Duplicate / cross-team roster rows** (the matchup-193 bug) | dashboard already log-guards it (`matchups.py`); root cause is a non-idempotent roster load leaving a player on two teams in one game | roster crawler/loader idempotency |

Numbers reproduce with the queries inline above.

### D1 — `last_season` never persisted (highest priority)

The column exists (`Player.last_season`), the nflverse client reads it
(`crawlers/nflverse/client.py:274 last_season=_opt_int(row.get("last_season"))`), and the
runner maps it into the upsert dict (`crawlers/nflverse/runner.py:264`). Yet every row is
NULL. So one of these is true — confirm which:

1. The nflverse **player-metadata** crawl (the path through `_upsert_players`) has not been
   run against this DB; players were created only via the **stub** path
   (`_create_stub_players`, no `last_season`) and the **nfl_com** path
   (`crawlers/nfl_com/league.py:426`, no `last_season`). → Re-run the metadata crawl so
   `_upsert_players` updates existing rows on the `gsis_id` conflict.
2. `load_players` rows don't actually carry a `last_season` key under that name (column
   drift in the nflverse source) → `row.get("last_season")` silently yields `None`. Verify
   the source column name and fix the mapping.
3. `upsert()`'s `update_cols` excludes `last_season` for these rows. (`update_cols`
   defaults to "every input column except the conflict key", so this is unlikely — but
   confirm the metadata path passes `last_season` in its `update_cols`.)

**Done when:** `last_season` is populated for every player nflverse knows
(`load_players`), and the metadata crawl is idempotent so a re-run keeps it populated.
Players genuinely absent from nflverse may stay NULL — that's an honest gap, not a bug.

### D2 — `rookie_year` gaps

Same population path as D1; many of the 322 nulls are the D4 ghost players, but **88 are
league-rostered** and should resolve once the metadata crawl runs. Audit the residual: are
they pre-nflverse-coverage players, or normalizer ID-match misses (player exists under a
different `gsis_id`/override)?

**Done when:** rookie_year is populated for every league-rostered player nflverse can
identify; remaining nulls are documented as a true source gap.

### D3 — `is_active` semantics + stale `nfl_team`

Today `is_active` is set from a one-shot nflverse `status` snapshot
(`runner.py:266 is_active = (status or "").upper()=="ACT" or status is None`) — note the
`status is None → True` fallback makes unknowns *active*. The dashboard renders an
active/retired badge and offers an active/retired filter off this, so the flag needs to
mean something stable. Decide and document the intended semantics, e.g.:

- `is_active` = "on an NFL roster as of the latest crawl" (a *current-NFL* fact), **or**
- derive a separate, more useful **league-relevance** signal (see D4 / dashboard plan),
  and stop overloading `is_active`.

Also: `nfl_team` is a single mutable "current team" column — for a retired player it's
whatever team they were last attached to in the snapshot, which reads as wrong in a
historical index. Confirm whether `nfl_team` is meant to be "current" or "last known," and
make the crawler not leave a stale current-team value on players nflverse now reports as
inactive/retired.

**Done when:** `is_active` has a documented, stable definition; the `status is None → True`
fallback is reconsidered; a player nflverse reports as retired is not left `is_active=1`
with a live-looking `nfl_team`.

### D4 — ghost players / ingestion scope

879 players were never rostered in this league and never scored a fantasy point here. They
exist because nflverse metadata + stubs ingest a broad NFL-player universe. The runner
*does* have a league-scope filter (`runner.py:210–250`, drops players whose
`last_season < league_start_year`) — but that filter is defeated by D1: **with
`last_season` NULL, the era filter can't drop anyone** (`last_season is not None` guard).
So fixing D1 will let this filter actually work and should shrink the ghost set.

Decide the policy and document it in `docs/03_DATA_ACCESS.md` (dashboard side mirrors it):

- Keep ghosts in the DB but make "league relevance" queryable (preferred — see below), or
- Tighten ingestion so non-league players aren't persisted at all.

**Recommended (low-risk, additive):** expose a way for the dashboard to ask "is this
player league-relevant?" without it doing its own joins. Either:
- **(a)** a read-only repository helper `search_players(..., league_relevant: bool|None)`
  that filters to players with ≥1 `team_rosters` row (optionally OR ≥1 scored row), **or**
- **(b)** a derived/materialized `players.first_rostered_season` / `last_rostered_season`
  (NULL ⇒ never rostered) the dashboard can read and surface.

Option (b) also kills D3's ambiguity (you can show "rostered 2012–2018" instead of a
misleading active badge) and is the cleaner long-term answer.

**Done when:** the dashboard can request a league-relevant-only player index through the
repository (no dashboard-side business logic), and the policy is written down.

### D5 — roster load idempotency (the "wrong owner" bug)

`team_rosters` now has `UNIQUE(season_year, week, player_id)` (models.py:291), which
*should* prevent a player on two teams in one week. The matchup-193 contamination that
prompted the dashboard's log-guards suggests either pre-constraint rows survived, or a
loader writes rows in a way that dodges the constraint. Audit:

```sql
-- same player, same season+week, >1 team (should be zero under the constraint)
SELECT season_year, week, player_id, COUNT(DISTINCT team_id) c
FROM team_rosters GROUP BY season_year, week, player_id HAVING c > 1;
```

If any rows exist, they're stale pre-constraint data → clean them and confirm the loader
is idempotent on re-ingest. The dashboard's guard should stay (defense in depth) but should
stop finding anything to warn about.

**Done when:** the query above returns zero rows; re-ingesting a week is idempotent; the
dashboard's `home/away share a player` guard no longer fires on real data.

## One coordinated API addition

The dashboard wants to show **"last year played"** on the player detail page. The model has
`last_season` but **`PlayerOut` (`api/schemas.py:338`) does not expose it.** Once D1 is
fixed, add `last_season: int | None = None` to `PlayerOut` (additive, backward-compatible).
The dashboard will regenerate its client and render it. Coordinate the merge so the
dashboard's `gen:api` drift check is run against the new schema in the same cycle.

## Suggested order

D1 → D2 (same crawl) → D5 (data cleanup) → D4 (scope policy + relevance helper) →
D3 (is_active semantics) → `PlayerOut.last_season`. D1 unblocks the era filter that
shrinks D4, so do it first.
