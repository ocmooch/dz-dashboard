# Zero Score / Gap Audit Plan

## Goal

Give the dashboard a clear, testable story for player score display:

- Non-zero scores are always shown accurately anywhere weekly player scoring is relevant.
- True zeroes are distinguishable from BYE / did-not-play / unresolved data gaps.
- Views where weekly availability is irrelevant are dismissed categorically.
- Remaining unresolved rows are documented for upstream investigation or explicit UI treatment.

## Scope

Relevant views are week-scoped views that claim to show a player result for a specific fantasy
week:

- Box score: `/matchups/{matchup_id}/`
- Team roster when a concrete week is selected
- Player weekly scoring/detail rows
- Stats explorer when filtered to weekly player rows

Out of scope by design:

- Season/career summaries, records, standings, manager pages, draft pages, search, and league
  history. Injury and in/out designations are not meaningful there because they pertain only to
  concrete in-season schedule weeks.

## Current State

Box score handling is now the strongest path:

- non-zero scored row -> actual points
- scored zero with stat row -> true zero
- opponent `Bye` -> `Bye`
- non-defense roster row with no NFL.com score and no stat row -> `did_not_play` / `Out`
- league zero but nflverse material points -> unexpected-zero warning
- missing DST/scoring reconstruction row -> data gap, not fake zero
- unscored season -> page-level data gap

Live DB spot audit on 2026-06-15 found, among roster rows tied to actual matchup weeks in scored
seasons after upstream identity and D/ST reconstruction fixes:

- 38,950 scored non-zero rows
- 600 true zero rows with a raw stat row
- 2,738 BYE zeroes
- 4,239 missing non-defense rows classified as scored-season DNP/Out
- 0 missing DST rows in actual matchup weeks, though the code still preserves the gap path
- 0 unexpected zeroes

## Audit Steps

1. Build a reusable read-only audit script.
   - Input: live dashboard DB.
   - Restrict to actual fantasy matchup team/weeks, not draft/week-0 snapshots.
   - Emit counts and examples for: non-zero scored, true zero with raw stat row, BYE zero,
     did-not-play missing row, unexpected zero, missing DST, and whole unscored season.

2. Compare backend endpoints.
   - Box score: confirm current invariant.
   - Team roster: verify whether week-specific rows use the same zero/DNP/BYE semantics or need
     the shared classifier.
   - Player weekly scoring/detail: verify zero rows and missing rows are labeled consistently.
   - Stats explorer: verify weekly rows do not collapse null into zero or hide non-zero values.

3. Categorize every endpoint/view.
   - `covered`: already uses the canonical semantics.
   - `needs_shared_classifier`: weekly player rows exist but use older null/zero treatment.
   - `safe_ignore`: no week-scoped player result is displayed.
   - `upstream_data`: dashboard cannot decide without Phase 1 data repair.

4. Add regression tests.
   - Backend invariant test for the canonical classifier and endpoint outputs.
   - Frontend component tests for `Out`, `Bye`, true `0.00`, unexpected zero, and real data gap.
   - Optional live-DB audit command documented as non-CI verification.

5. Investigate unresolved upstream rows.
   - The 2025 week 1 missing non-defense rows should be reviewed in Phase 1 to decide whether
     NFL.com authoritative `0.0` points should be persisted for all DNP roster rows.
   - Any future missing DST rows remain a separate scoring reconstruction issue and should stay
     a dashboard gap until resolved upstream.

## Done When

- Every dashboard player-score surface is classified as covered, safe-ignore, or unresolved with
  examples.
- Week-scoped views share one backend classification rule or have a documented reason they do not.
- Non-zero player points are never hidden behind gaps in relevant views.
- True zero, BYE, did-not-play, and real scoring gaps have visible and tested treatments.

## Build Coverage Pass (2026-06-15)

Reusable audit command:

```bash
uv run python scripts/audit_zero_score_gaps.py --examples 5
```

Endpoint/view categorization:

| Surface | Status | Evidence / rule |
| --- | --- | --- |
| Box score `/matchups/{matchup_id}/` | covered | Uses `classify_zero()` plus per-row `available/reason`: non-zero points show normally, BYE and DNP zeroes render as status labels, organic zeroes render as `0.00`, unexpected league-0/nflverse-nonzero rows carry a warning, missing DST rows stay `DataGap`. |
| Team roster `/teams/{team_id}/roster?week=N` | covered | Now uses the same authoritative-points preference and `classify_zero()` as box score. In scored seasons, missing non-DST roster rows become DNP zeroes; missing DST rows remain null/gap. |
| Player scoring `/players/{player_id}/scoring?season=Y` | covered | Week rows are built from authoritative roster points plus scored rows and carry `zero_reason` / `zero_detail`; unscored seasons return page-level `available:false`. Missing unrostered weeks are intentionally absent rather than invented. |
| Stats explorer weekly leaders `/stats/top-scorers?week=N` | safe_ignore | This is a top-scorer leaderboard over existing scored rows, not a roster/result ledger. It cannot display DNP/BYE rows and does not collapse missing rows into zero. |
| Stats explorer season totals `/stats/season-totals` | safe_ignore | Season aggregate; weekly availability is irrelevant by scope. Unscored seasons return an empty/gap state, not zero-filled player totals. |
| Season/career summaries, records, standings, manager pages, draft, search, league history | safe_ignore | These pages do not claim to show a concrete weekly player result. |

Upstream exception resolution:

- The six previously unexpected NFL.com `0.0` rows were resolved upstream instead of forced on the
  dashboard. Root causes were:
  - Christine Michael NFL.com rows and player id `2539322` were stamped onto real Giants RB Michael
    Cox. The rows were moved to the existing Christine Michael identity, Michael Cox was left with
    only his real 2013/2014 rows, a durable override was inserted, and the resolver now requires
    abbreviated NFL.com names to structurally match first-initial + last name.
  - D/ST `special_teams_tds` was scored twice when a league had both individual return-TD and D/ST
    return-TD rules. The scorer now applies shared return-TD keys by row context.
  - D/ST `points_allowed` was using final score. Upstream team-defense reconstruction now derives
    fantasy D/ST points allowed from play-by-play when available: opponent defensive TDs and safeties
    against the offense are excluded, while kickoff/punt/blocked-punt/FG return TDs remain charged
    to the D/ST unit.
- The 2010 D/ST cases showed no evidence of an in-season scoring-settings change or manager score
  edit. Manager activity had scoring-setting updates in July 2010 before the season, then no
  in-season 2010 scoring-setting change around the affected weeks.
- Future missing DST rows remain `upstream_data`: the dashboard preserves them as per-row scoring
  reconstruction gaps instead of inferring zero.

Live audit command result on 2026-06-15 (`--examples 5`): 46,527 scoped roster rows; 38,950
non-zero scored rows; 600 true zeroes with a raw stat row; 2,738 BYE zeroes; 4,239 DNP zeroes;
0 unexpected zeroes; 0 missing DST rows in actual matchup weeks. The DNP count includes both
authoritative NFL.com `0.0` rows with no nflverse stat line and rows with neither source that the
dashboard classifies as DNP in scored seasons.
