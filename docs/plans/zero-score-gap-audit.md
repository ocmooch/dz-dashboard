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
seasons:

- 38,934 scored non-zero rows
- 7,574 scored zero rows
- 19 missing non-defense rows, all 2025 week 1; these are now box-score `Out` rows
- 0 missing DST rows in actual matchup weeks, though the code still preserves the gap path

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
