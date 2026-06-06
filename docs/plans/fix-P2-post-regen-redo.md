# fix-pass P2 redo - Post-regen data honesty revalidation

Plan doc for redoing fix-pass **P2** after the 2026-06-06 `fantasy.db` regeneration changed the
coverage premise. Use this as the BUILD/VERIFY guide for the P2 honesty layer; keep
`docs/plans/fix-P2-honesty.md` as the historical PR #31 plan.

Base: `dev` after PR #33 (`feature/fix-F51-current-season-scoring`) is merged.
Branch: `feature/fix-P2-post-regen-redo` -> PR to `dev`.

## Why this redo exists

The original P2 pass assumed `player_stats_scored` existed only for 2016-2025. The regenerated DB
now has per-player scoring for **2010-2025**, and `/v1/seasons` reports `is_scored:true` for every
completed season in that range. That means the old P2 tests and copy that talked about a
pre-2016 unscored era are stale.

The current truth is data-driven:
- Completed seasons 2010-2025 are scored.
- The current/in-progress season may be unscored.
- `is_scored` means "per-player fantasy scoring exists for this season", not "all season data is
  complete".
- No frontend code should hardcode 2016, 2025, or a pre-2016 scoring gap.

## Done when

No view describes 2010-2015 as missing per-player scoring; the only unscored affordances render
for seasons whose `is_scored` flag is actually false; records/player windows derive from current
coverage; the coverage harness asserts the post-regen truth; real-DB click-through confirms 2010,
2015, 2025, and the current season behave honestly; full gate is green.

## Scope

Re-verify and, where needed, adjust the P2 findings affected by the regen:
- **F-16/F-35/F-33:** matchup, team, stats, and shared `DataGap` copy must be season-agnostic and
  gated only by `is_scored`.
- **F-26:** player detail must show an unscored-tenure affordance only when a player's rostered
  span has no scored seasons, derived from season coverage.
- **F-43:** the coverage harness must assert the new scored coverage instead of the old
  pre-2016 absence.
- **F-48:** keep `dst_scoring_complete` as a presence flag; do not turn the nflverse DST
  yards/sacks value concern into an end-user gap.
- **F-22 dependency:** player-record windows should use the data-driven scored window
  (now 2010-2025 on the regenerated DB), while team-record windows continue to use all seasons
  with team totals.

Out of scope:
- Mutating or regenerating the DB.
- Any Phase 1 scoring-rule changes.
- `seasons.status` being `in_progress` for every row (F-52, upstream/danger-zone).
- API response-shape changes unless a failing test proves the current schema cannot express the
  truth.

## Files to touch

Frontend:
- `web/src/design-system/index.tsx` - confirm `season_unscored` and the shared unscored-season
  note are year-agnostic; remove any remaining `PRE2016_*` naming or copy.
- `web/src/features/matchups/MatchupsPage.tsx` - unscored banner appears only when
  `!data.is_scored`; copy scopes the gap to player box-score scoring for that season.
- `web/src/features/teams/TeamPage.tsx` - roster/points copy must distinguish complete roster rows
  from unavailable player points.
- `web/src/features/stats/StatsPage.tsx` - empty/gap copy must not imply pre-2016 absence.
- `web/src/features/players/PlayerDetailPage.tsx` - keep the generalized `unscored_tenure`
  predicate; verify it does not fire for 2010-2025-only players on the regenerated DB.
- `web/src/app/shell/AppShell.tsx` - season selector label should only mark seasons whose
  `is_scored` is false.

Backend/tests:
- `tests/test_coverage_integrity.py` - rewrite stale assertions:
  - scored seasons include all completed fixture seasons with scored rows;
  - no hardcoded pre-2016 absence;
  - unscored present seasons, if any, may still have team scores and rosters;
  - records team window spans team-total seasons;
  - records scored window equals the seasons with `is_scored:true`;
  - DST presence flag remains equivalent to scored seasons carrying DEF scored rows.
- `tests/test_records.py` or the existing records test module - add/adjust a known-answer case
  proving player records can come from the earliest scored season in the fixture.
- Existing frontend tests in `web/src/features/{matchups,teams,stats,players}/` and shell tests -
  update stale pre-2016 expectations to data-driven unscored-season cases.

Docs/progress:
- `docs/03_DATA_ACCESS.md` and `docs/04_ANALYTICS_MODEL.md` only if the build finds stale wording.
- `docs/reviews/2026-06-in-browser-review.md` - mark the P2 redo verification result and note any
  residual findings.
- `docs/plans/REVIEW_FIXES_ROADMAP.md` - add the BUILD/VERIFY consideration line.
- `PROGRESS.md` - update current state, next step, and files that matter now.

## Test plan

Scoped BUILD tests:
- `uv run pytest tests/test_coverage_integrity.py -q`
- records test module containing the F-22 window assertion
- affected frontend test files only while iterating

VERIFY gate:
- `uv run pytest tests -q`
- `uv run ruff check -q && uv run ruff format --check`
- `uv run mypy src/ff_dashboard`
- `git grep -nE "INSERT|UPDATE |DELETE |upsert|crawler|normalizer" src/ff_dashboard`
- in `web/`: `npm run gen:api && git diff --exit-code web/src/lib/api`
- in `web/`: `npm run typecheck && npm run lint && npm run test`
- `npm run test:e2e` only if the changed views are already covered by the P11 journeys or the
  build changes navigation behavior.

## Manual real-DB click-through

Use the regenerated real DB read-only. Confirm:
- 2010 and 2015 no longer show "no player scoring" or pre-2016 gap language.
- A known 2010-2015 player with scored rows renders a scoring chart or player records normally.
- 2025 still renders scored data.
- The current season renders an unscored affordance only if its `is_scored` flag is false.
- Records/About copy report the scored window from coverage, not hardcoded years.

## Build order

1. Update the coverage harness first so stale assumptions fail locally.
2. Fix backend records/window assertions if the harness exposes stale coverage logic.
3. Update shared frontend copy and the feature tests that encode old pre-2016 language.
4. Run scoped tests, then the VERIFY gate once.
5. Update progress/review/roadmap docs and open the PR with the required trailers.
