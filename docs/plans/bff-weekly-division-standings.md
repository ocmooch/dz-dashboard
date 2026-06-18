# BFF-Owned Weekly Division Standings

## Session model

This post-roadmap product slice follows `PLAN → BUILD → VERIFY`.

- PLAN: this document only.
- BUILD: historical source artifact, BFF analytics/API, Record-lens UI, and scoped tests.
- VERIFY: full dashboard gate, e2e/visual coverage, and manual inspection of 2010, 2011,
  2018, 2019, and 2020.

## Scope

For 2010–2019, replace the reduced legacy conference card and overall Record table with
full-width division tables ordered by the reviewed NFL.com historical standings source. Reuse
the dashboard's existing standings rollup for all weekly totals and derive cumulative
in-division W-L-T from opponent-linked regular-season matchup rows.

Midseason division order must be the existing `compute_standings()` order filtered into each
division. At the completed regular-season view, division and overall ranks must come from the
committed NFL.com source artifact. The artifact, not the Phase 1 database, owns historical
division membership and source ranks.

For 2020 onward, keep the existing single-table Record layout. Add one Record-lens
`WeekStepper` for every season and send its selected week to standings, insights, and historical
division requests. Keep the Power lens and its independent week behavior otherwise unchanged.

The application remains read-only. Authenticated HTML, cookies, and credentials are never
committed or used at runtime.

## Done when

- A reviewed artifact pins all 2010–2019 division names, source order, NFL.com team IDs,
  final division ranks, final overall regular-season ranks, source URLs, and capture dates.
- Every source team maps exactly once through `teams.team_abbrev`; missing, duplicate, and
  multi-division assignments return an explicit mapping gap.
- `season_conferences(session, season_id, through_week=None)` returns exact weekly overall and
  in-division records, PF, PA, Win%, streak, overall rank, and division rank.
- Midseason division ordering preserves `compute_standings()` order. Completed regular-season
  ordering uses the captured source ranks.
- The Record lens synchronizes standings, insights, and divisions to one URL-backed week.
- Historical seasons render stacked full-width division tables with `#`, `OVR`, `DIV`, Team,
  Record, Win%, PF, PA, conditional Finish, and Streak.
- 2020+ retains the current single-table layout; the reduced `Conference Standings` card is gone.
- Backend known-answer, contract, component, e2e, desktop visual, and mobile visual tests pass.
- Full dashboard gate is green and 2010, 2011, 2018, 2019, and 2020 are manually inspected.

## Historical source artifact

Create:

- `src/ff_dashboard/data/historical_divisions.json`
- `src/ff_dashboard/analytics/historical_divisions.py`
- `scripts/audit_historical_divisions.py`
- `tests/test_historical_divisions.py`

Normalized JSON shape:

- top level: `schema_version`, `reviewed_at`, `seasons`
- season: `season`, `source_url`, `captured_at`, `divisions`
- division: `division_number`, nullable `name`, ordered `teams`
- team: `nfl_team_id`, `final_division_rank`, `final_overall_regular_season_rank`

`historical_divisions.py` loads and validates the committed artifact and exposes immutable
season lookups. Validation rejects:

- years outside 2010–2019 or missing years in that range;
- duplicate/missing division numbers;
- duplicate NFL.com team IDs within a season;
- a team assigned to multiple divisions;
- non-contiguous division or overall ranks;
- any season other than 12 total teams;
- 2010 other than three divisions of four;
- 2018 other than two named divisions of six.

The optional audit script is read-only and requires an explicit cookie/environment input. It
re-fetches each artifact `source_url`, parses the regular-standings view, compares normalized
membership/names/ranks to the committed artifact, prints drift, and exits non-zero on mismatch.
It must not write the database, artifact, HTML, cookie, or credentials.

The artifact source URLs use:
`https://fantasy.nfl.com/league/36271/history/{year}/standings`.

## Analytics

Change `src/ff_dashboard/analytics/conferences.py`.

Public signatures:

```python
def conference_map(
    session: Session, season_id: int
) -> dict[int, tuple[int | None, str | None]]

def season_conferences(
    session: Session,
    season_id: int,
    through_week: int | None = None,
) -> dict[str, Any] | None
```

Implementation:

1. Resolve the season; return `None` when absent.
2. Return `available=false`, `reason=no_conferences_this_season` for 2020+.
3. Load that year's artifact and map each `nfl_team_id` through the season's
   `teams.team_abbrev` using read-only ORM/SQL queries.
4. Return `available=false`, `reason=historical_division_mapping_gap`, plus structured
   `mapping_issues`, if a source ID is missing/duplicated, an internal team maps more than once,
   a source team is assigned to multiple divisions, or the mapped set differs from the season's
   standings set.
5. Call `compute_standings(session, season_id, through_week)` exactly once. Its row order is the
   weekly overall order and supplies W-L-T, Win%, PF, PA, streak, owner/team labels, and Finish.
6. Count division W-L-T from regular-season `matchups` rows through the returned
   `through_week`, only when `opponent_team_id` maps to the same artifact division. Count each
   team-side row independently, matching existing standings aggregation semantics.
7. Midseason: set `overall_rank` from the existing standings row `rank`; filter that ordered list
   into divisions and enumerate `conference_rank`.
8. Completed regular season: override `overall_rank` and `conference_rank` with artifact ranks
   and sort by artifact division rank. Do not overwrite postseason `final_rank`, which remains
   the Finish column's source.
9. Return artifact divisions in source `division_number` order.

`conference_map()` uses the same artifact mapping and returns `{}` for 2020+ or any mapping gap,
preserving bracket's defensive behavior without fabricating membership.

Known-answer analytics tests:

- 2010: three divisions of four, unnamed where sourced unnamed.
- 2018: two named divisions of six.
- 2020: unavailable with `no_conferences_this_season`.
- Early, middle, and final regular-season weeks: total W-L-T and division W-L-T.
- PF, PA, streak, overall rank, and division rank equal the standings rollup/order midseason.
- Final division and overall ranks equal every artifact row.
- Missing source team, duplicate `team_abbrev`, multi-division source assignment, and extra DB
  standings team each produce `historical_division_mapping_gap`.

Fixture changes belong in `tests/conftest.py` only where required to encode historical divisions
and hand-checkable same-division/cross-division matchups.

## API contract

Change:

- `src/ff_dashboard/api/schemas.py`
- `src/ff_dashboard/api/routes/seasons.py`
- generated `web/src/lib/api/schema.d.ts` via `npm run gen:api`
- endpoint tests in `tests/test_p2_endpoints.py`

Route:

`GET /v1/seasons/{season_id}/conferences?through_week={week}`

`SeasonConferences` adds:

- `through_week`
- `regular_season_weeks`
- `mapping_issues`

Each `ConferenceTeam` adds:

- `overall_rank`
- `division_wins`
- `division_losses`
- `division_ties`

Keep `conference_rank` as the API's division-rank field for compatibility. Keep `final_rank` as
postseason Finish. `ConferenceSection` continues to carry source order/name and may retain the
existing `conference_id` as a deterministic dashboard-local identifier derived from
`season/division_number`; no database conference model is assumed.

Contract tests pin the historical happy path, weekly query propagation, 2020 gap, mapping-gap
shape, and 404.

## Record-lens UI

Change:

- `web/src/features/standings/StandingsPage.tsx`
- `web/src/features/standings/StandingsPage.test.tsx`
- `web/src/lib/queryKeys.ts`

Use the existing `Tabs`, `WeekStepper`, `Card`, `CardHeader`, `Chip`, `RecordLine`, `Trophy`,
`Badge`, `DataGap`, `Skeleton`, and `ErrorState` primitives.

Behavior:

- `?week=` is the Record lens's selected week as well as the existing Power lens week.
- Record defaults to `regular_season_weeks`; switching lenses preserves a valid week.
- Record queries use week-aware keys and pass `through_week` to standings, insights, and
  conferences.
- The Record header/card owns the `WeekStepper`; all three requests update together.
- `showFinalPlacement` is true only when selected week equals `regular_season_weeks`, never merely
  because `final_rank` exists in the payload.
- Historical `available=true`: render one full-width card/table per division, vertically stacked
  in source order. Columns are `#`, `OVR`, Team, Record, Win%, PF, PA, DIV, conditional Finish,
  Streak.
- Historical mapping gap: render `DataGap` with the returned reason; do not fall back to an
  apparently complete overall table.
- 2020+: render the current overall table with its existing columns and presentation.
- Remove the compact `ConferenceTable` and reduced `Conference Standings` card.
- Robbed & Blessed uses the selected week. Standings timeline remains full-season and unchanged.
- Power lens rendering, model, table, and timeline remain unchanged.

Component tests:

- 2010 historical response renders three stacked full-width tables.
- 2018 renders two named six-team tables.
- Historical tables expose `DIV` and `OVR`.
- Week navigation updates all three Record request query params and hides Finish before the final
  week.
- Completed-season view shows Finish.
- Mapping gap renders `DataGap`.
- 2020 response retains one existing overall table and no division headings.
- Power lens behavior remains covered by existing tests.

## E2E and visual coverage

Change:

- `web/e2e/journeys.spec.ts`
- `web/e2e/visual.spec.ts`
- committed Playwright baselines generated by the existing update command

Add a journey that selects a historical season, confirms division headings/`DIV`/`OVR`, steps to
an earlier week, verifies the URL and visible records change, and confirms Finish disappears.

Add deterministic historical standings desktop and mobile screenshots. Keep the existing modern
standings screenshot to guard the unchanged 2020+ layout. Mask only the existing live data-status
surface.

## Documentation and progress

Update:

- `docs/04_ANALYTICS_MODEL.md` with the source-vs-derived rank boundary and division-record rule.
- `docs/05_API_CONTRACT.md` with `through_week` and the expanded conference response.
- `docs/07_PAGES_AND_VIEWS.md` with historical stacked tables and synchronized Record week.
- `docs/08_TESTING_STRATEGY.md` only if fixture/visual policy needs clarification.
- `docs/ACTIVE_WORK.md` to close the dead-conferences item.
- `PROGRESS.md` at BUILD checkpoints and final verification.

## Verification

Scoped iteration:

```bash
uv run pytest tests/test_historical_divisions.py tests/test_p2_analytics_unit.py tests/test_p2_endpoints.py -q
cd web && npm run test -- StandingsPage.test.tsx
```

VERIFY uses `.claude/skills/green-gate/`:

- backend pytest, ruff check/format, mypy, and write-safety grep;
- generated API drift, frontend typecheck/tests;
- Playwright e2e and visual suite;
- manual real-DB inspection of 2010, 2011, 2018, 2019, and 2020 at early/middle/final weeks.

