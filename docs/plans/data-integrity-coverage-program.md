# Data Integrity & Coverage Program Plan

Status: PLAN complete, BUILD in progress.

## Scope

Implement the dashboard half of the three handoffs under `docs/handoffs/`:

- `00-data-integrity-program.md`: preserve the mental model and codify the anti-whack-a-mole rule.
- `player-identity-resolution.md`: add read-only split detection now; consume upstream canonical identity when present.
- `data-coverage-matrix.md`: add `/v1/meta/coverage`, make projection gaps self-explaining, and pin the current fixture truth with tests.

The upstream canonical merge remains in `../danger-zone` on a separate feature branch. This dashboard branch must not write to the DB and must not reconcile identities itself.

## Files To Touch

- `src/ff_dashboard/analytics/coverage.py`: coverage matrix, relevance summary, unresolved identity split detection.
- `src/ff_dashboard/analytics/matchups.py`: projection coverage reason on box-score players.
- `src/ff_dashboard/api/routes/health.py`: `GET /v1/meta/coverage`.
- `src/ff_dashboard/api/schemas.py`: matrix schemas and optional box-player projection gap fields.
- `web/src/design-system/index.tsx`: reason-label copy for matrix-driven gaps.
- `web/src/features/matchups/BoxScorePage.tsx`: render projection/value gaps from BFF reasons.
- `tests/conftest.py`: fixture rows for projections and one identity split candidate.
- `tests/test_coverage_integrity.py`, `tests/test_p1_bootstrap.py`, `tests/test_p5_*`: contract and originating-gap tests.
- Docs: `docs/08_TESTING_STRATEGY.md`, `docs/03_DATA_ACCESS.md`, `PROGRESS.md`, `docs/ACTIVE_WORK.md`.

## API Shape

Route: `GET /v1/meta/coverage`

Response model: `Envelope[CoverageMatrix]`

Top-level fields:

- `relevance`: included/excluded player tallies and unresolved identity split candidates.
- `feeds`: feed-level season/week cells for `rosters`, `scored_stats`, `injuries`, `projections`, `transactions`, and `availability`.
- `reason_codes`: UI vocabulary for self-explaining gaps.

Box player additions:

- `projection_available: bool`
- `projection_reason: str | None`

The frontend only renders these fields; all coverage decisions remain in the BFF.

## Tests

- Coverage contract: fixture-derived feed ranges, projections only in the fixture's covered week, scored stats only in scored seasons, injuries excluded when outside league-relevance.
- Relevance regression: league-scoped players stay rostered; unresolved split candidate is counted.
- API contract: `/v1/meta/coverage` returns the matrix and `/v1/meta` remains backward compatible.
- Box-score gap: uncovered projection cells render a `DataGap` reason; covered cells render values.

## Done When

- `/v1/meta/coverage` returns a data-driven relevance + coverage matrix with reason codes.
- Identity split detection is visible and countable, without dashboard-side identity union math.
- Matchup projection gaps explain why they are empty.
- Focused backend and frontend tests pass; full green gate is run in VERIFY.
- The anti-whack-a-mole rule is recorded in testing/data-access docs.
