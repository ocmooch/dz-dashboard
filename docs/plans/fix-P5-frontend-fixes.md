# fix-pass P5 — Frontend navigation & presentation fixes

Plan doc for fix-pass **P5** from the 2026-06 in-browser review.

Base: `dev` after PR #36 (`feature/docs-consolidation`) is merged.  
Branch: `feature/fix-P5-frontend-fixes` -> PR to `dev`.

## Scope

P5 is a frontend-heavy correctness/presentation pass. It fixes broken controls, confusing labels,
navigation dead ends, chart readability, draft-board layout, and one small player-index contract
cleanup. It does **not** add new analytics models; only F-24 changes the BFF contract by removing
the public `scope=all` player-index option and the `has_scored` row field.

Verbatim review done-when:

> selectors/links work (incl. pre-2016); scope/has_scored gone; sort toggles; week selectable;
> draft board is a 12-col snake; timelines legible; typecheck+lint+vitest green; gen:api drift
> clean; click-through verified.

Sharpened for BUILD/VERIFY:

- The selected season/year controls actually refetch or navigate to data for that selection.
- No public players UI or `/v1/players` contract surface exposes never-rostered players or
  `has_scored`.
- Shared controls (`WeekStepper`, `RankFlow`/timeline tooltip, global search dropdown) improve all
  consuming views without per-page drift.
- Presentation fixes render honest gaps, never zeros/dashes for unavailable data.

## Findings

| Finding | Build action |
|---------|--------------|
| F-34 | Wire the team page's season-year selector to actual page state/navigation. |
| F-36 | Make schedule matchup links degrade gracefully for historical/current `box-score.available:false` cases instead of landing on an error. |
| F-05 | Add manager -> latest roster reachability via owner seasons -> latest `team_id` -> `/teams/{team_id}`. |
| F-24 | Remove `scope=all` and `has_scored` from `/players` API schema/route and the Players UI. |
| F-07 | Make Managers index sorting toggle asc/desc. |
| F-15 | Add direct week selection to shared `WeekStepper`. |
| F-46 | Make the global search result menu scrollable for many hits. |
| F-14 | Color matchup margins per side: winner/positive green, loser/negative red. |
| F-11 | Replace rivalry snapshot compact "Ng" copy with clear "N GP" / "N games" labeling. |
| F-40 | Render the draft board as a 12-column snake grid. |
| F-30 | Make Stats default to season totals; keep weekly leaders reachable. |
| F-04 | Surface final standings/playoff placement on completed standings rows from existing `final_rank` / champion data. |
| F-28 | Collapse player ownership timeline UI into shorter scannable blocks. |
| F-02 | Improve standings timeline tooltip: "Week N", rank-ordered series for hovered week, distinct colors. |
| F-42 | Apply the same timeline legibility improvements to the power timeline. |

## Build slices

Keep BUILD scoped and commit only after focused tests pass. Suggested order:

1. **Contract + players cleanup (F-24).** Remove the public `scope` query parameter and
   `has_scored` field from BFF schemas/routes and generated client, then simplify `PlayersPage`.
   This creates expected API client drift.
2. **Shared controls/charts (F-15, F-46, F-02, F-42).** Upgrade `WeekStepper`, global search menu
   scrolling, and `RankFlow`/timeline tooltip/color behavior before page-specific work consumes it.
3. **Navigation fixes (F-34, F-36, F-05).** Wire team season selection, box-score gap degradation,
   and manager latest-roster links.
4. **Page presentation fixes (F-07, F-14, F-11, F-40, F-30, F-04, F-28).** Finish local UI polish
   with focused feature tests.

## Files to touch

### API / contract (F-24 only)

| File | Change |
|------|--------|
| `src/ff_dashboard/api/routes/players.py` | Remove the public `scope` query parameter; always call `list_player_index(..., scope="league")`. |
| `src/ff_dashboard/api/schemas.py` | Remove `PlayerIndexRow.has_scored` and `PlayerIndexResponse.scope` if no longer useful to clients. |
| `src/ff_dashboard/analytics/players.py` | Keep internal `scope` support only if tests still need `scope=all` as a coverage guard; otherwise restrict the public route to league scope. |
| `tests/test_p2_endpoints.py` | Update endpoint contract assertions; no `/v1/players?scope=all` public behavior. |
| `tests/test_coverage_integrity.py` / `tests/test_p2_analytics_unit.py` | If keeping internal `scope=all`, preserve analytics-level coverage tests; if removing it entirely, replace with a direct never-rostered exclusion fixture assertion. |
| `web/src/lib/api/schema.d.ts` | Regenerated only by `npm run gen:api`; never hand edit. |

### Frontend shared pieces

| File | Change |
|------|--------|
| `web/src/design-system/index.tsx` | `WeekStepper` gets a direct week select/list while preserving prev/next. |
| `web/src/design-system/index.test.tsx` | WeekStepper direct-select coverage. |
| `web/src/charts/index.tsx` | Rank/timeline tooltip label, hover ordering, and enough distinct series colors. |
| `web/src/charts/chartTheme.ts` | 12-team categorical palette if the existing ramp repeats too early. |
| `web/src/charts/index.test.tsx` / `chartTheme.test.ts` | Chart wrapper regression coverage. |
| `web/src/features/search/GlobalSearch.tsx` | Scrollable results menu with keyboard behavior intact. |
| `web/src/features/search/search.test.tsx` | Many-result scrollability / keyboard navigation coverage. |

### Frontend page work

| File | Change |
|------|--------|
| `web/src/features/players/PlayersPage.tsx` | Remove scope selector and scored column; keep rostered span. |
| `web/src/features/players/players.test.tsx` | Remove scope/has_scored expectations; assert league-only index UI. |
| `web/src/features/teams/TeamPage.tsx` | Wire season selector; schedule links handle unavailable box scores; preserve roster-moves card. |
| `web/src/features/teams/team.test.tsx` | Season selector + schedule link/gap behavior. |
| `web/src/features/matchups/MatchupsPage.tsx` | Margin coloring per side; shared WeekStepper direct select. |
| `web/src/features/matchups/BoxScorePage.tsx` | `available:false` box-score state renders a team-total result/gap affordance instead of an error. |
| `web/src/features/matchups/matchups.test.tsx` | Margin color + box-score unavailable path. |
| `web/src/features/managers/ManagersPage.tsx` | Sort direction toggle. |
| `web/src/features/managers/ManagerProfilePage.tsx` | Latest roster/team link; clearer rivalry games label. |
| `web/src/features/managers/*test.tsx` | Sort toggle, latest-roster link, rivalry label tests. |
| `web/src/features/draft/DraftPage.tsx` | 12-column snake draft board. |
| `web/src/features/draft/DraftPage.test.tsx` | Round direction / 12-column board coverage. |
| `web/src/features/stats/StatsPage.tsx` | Default to season totals; weekly leaders remain reachable. |
| `web/src/features/stats/stats.test.tsx` | Default-mode coverage. |
| `web/src/features/standings/StandingsPage.tsx` | Final placement badges and improved timeline. |
| `web/src/features/power/PowerPage.tsx` | Improved timeline. |
| `web/src/features/power/PowerPage.test.tsx` | Timeline smoke/regression coverage if local behavior is testable. |

### Docs

| File | Change |
|------|--------|
| `docs/05_API_CONTRACT.md` | Reflect F-24 player-index contract cleanup. |
| `docs/06_DESIGN_SYSTEM.md` | Update `WeekStepper` / chart behavior if changed. |
| `docs/07_PAGES_AND_VIEWS.md` | Reflect changed page behavior for players, team links, draft board, standings/stats. |
| `docs/plans/REVIEW_FIXES_ROADMAP.md` | Mark P5 progress and append build considerations. |
| `docs/reviews/2026-06-in-browser-review.md` | Mark P5 findings resolved with PR number during VERIFY. |
| `PROGRESS.md` | Update current state / next / files that matter at checkpoint and merge. |

## API / schema details

F-24 is the only API-contract change:

- Route stays `GET /v1/players?name=&position=&nfl_team=&active=&limit=&offset=`.
- Remove the public `scope` query parameter; route always returns league-relevant players.
- Remove `has_scored` from player-index rows. Keep `first_rostered_season` and
  `last_rostered_season`.
- Run `npm run gen:api` and commit the expected generated-client diff.

Do **not** remove league-scoping enforcement from analytics/search. The app still must exclude
never-rostered players everywhere.

## Tests

Backend:

- `uv run pytest tests/test_p2_endpoints.py tests/test_coverage_integrity.py tests/test_p2_analytics_unit.py -q`
  after F-24 route/schema changes.
- Any additional focused test files affected by schema changes.

Frontend focused:

- `npm run test -- players`
- `npm run test -- design-system`
- `npm run test -- search`
- `npm run test -- teams`
- `npm run test -- matchups`
- `npm run test -- managers`
- `npm run test -- draft`
- `npm run test -- stats`
- `npm run test -- power`

VERIFY:

- Backend pytest + ruff + mypy.
- Frontend `npm run gen:api && git diff --exit-code web/src/lib/api` after committing generated
  changes, typecheck, vitest. `npm run lint` is N/A unless a lint script has been added.
- Browser click-through on the real DB:
  - team season selector changes the team/page data;
  - historical schedule link lands on a usable result/gap state;
  - manager index/profile can reach latest roster/team;
  - players page has no scope or scored UI;
  - search dropdown scrolls;
  - draft board is a 12-column snake;
  - standings/power timelines are legible;
  - stats lands on season totals.

## Out of scope

- P6 composition/insight work: F-01, F-03, F-08, F-09, F-18, F-21, F-29, F-38, F-41.
- UP work: ownership-succession history (F-06), player identity audit (F-25), real transaction log
  scrape / FAAB details (F-37 tier 2), season status repair (F-52).
- New backend analytics beyond the F-24 contract cleanup.

## Done-when checklist

- [x] P5 findings implemented and focused tests added/updated.
- [x] F-24 contract cleanup landed; generated API client regenerated and committed.
- [x] Full gate green.
- [x] Real-DB browser click-through completed for the P5 routes above.
- [x] `docs/05`, `docs/06`, `docs/07`, `PROGRESS.md`, roadmap row, and review findings updated.
- [ ] PR opened to `dev` with trailers.
