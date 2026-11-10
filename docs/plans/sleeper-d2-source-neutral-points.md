# Sleeper D2 — Source-neutral points (plan + as-built)

Scope: `docs/sleeper/02` §D2; hotspot row "scoring.py + direct `nfl_com_points` reads" in `00` §6.

**Done when (verbatim):** no surface reads `nfl_com_points` directly except through the upstream helper.

## Change

- `analytics/scoring.py`
  - `authoritative_week_points(roster, scored)` → alias of `queries.authoritative_week_points_expr`
    (`coalesce(platform_points, nfl_com_points, total_points)`). Signature and call sites unchanged.
  - `official_points(roster)` → alias of `queries.official_slot_points_expr` (replaces the private
    `nfl_com_points()` SQL reader).
  - `official_points_from_extra(extra)` → the same precedence for code that already holds a roster
    row's `extra_data` dict (box score, team weekly, player weekly). It is the one Python-side mirror
    of the upstream expression; a test proves it agrees with the SQL helper on every roster row.
- Direct readers moved onto those helpers:
  - `records.py` best player week (inline `json_extract("$.nfl_com_points")`);
  - `matchups._authoritative_points` (box score + team views via `teams.py`);
  - `players.py` weekly log.
- No contract change (no schema fields), so `gen:api` drift stays clean.

## Tests (`tests/test_d2_source_neutral_points.py`)

- Legacy parity: `authoritative_week_points` == old `coalesce(nfl_com_points, total_points)` on every
  legacy fixture roster row (and on the mixed-era DB's legacy rows).
- `official_points_from_extra` == `official_slot_points_expr` for every roster row of the mixed-era DB.
- A Sleeper-era box score shows each player's official points from `platform_points` (available,
  not a gap), and the starters sum to the matchup's official score.
- Unit: precedence `platform_points` > `nfl_com_points`; bools/strings/missing → `None`.
- Existing golden parity (`test_legacy_parity`, live manifest) stays green.
