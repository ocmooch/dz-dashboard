# fix-pass P6 plan - frontend insights, seasonality, and composition

## Scope

Re-curate the front door and high-value pages around season-aware modules and richer insights.
This is a BUILD plan for fix-pass P6, covering F-01, F-29, F-08, F-03, F-09, F-18, F-38,
F-21, and F-41.

Authoritative done-when from the review doc, sharpened for build:

- Home, player detail, and records are re-curated and season-phase-aware.
- The requested insight modules land without metric math in `web/`.
- Power keeps its dedicated view, drops from the home front door, has a more compelling
  team-level methodology, and documents its inputs.
- Any missing or unproven bracket/activity data renders as an honest `DataGap`, never as
  invented output.
- Focused backend/frontend tests pass during BUILD; full gate and real-DB click-through happen
  in VERIFY.

## Scope decisions

- Do not build a literal playoff bracket from frontend inference. `docs/05_API_CONTRACT.md`
  still marks `/v1/seasons/{season_id}/bracket` as not implemented and caveated, and F-49 keeps
  bracket metadata partly upstream. Home should show an off-season "last season finish" module
  from proven season/standings/championship data, with a `DataGap` if a true bracket is required
  but unavailable.
- Keep P6 additive where possible. Contract changes are allowed only for explicit insight fields
  or endpoints below, followed by `npm run gen:api`; never edit `web/src/lib/api/` by hand.
- Season phase is a presentation selector, not a standings or scoring metric. It should be shared
  between home and player detail and should not rely on `seasons.status` while F-52 is open.

## Files to touch

Plan-level implementation targets:

- `web/src/lib/seasonPhase.ts` and `web/src/lib/seasonPhase.test.ts` - shared season-phase helper.
- `web/src/features/home/HomePage.tsx` - F-01 re-curation.
- `web/src/features/players/PlayerDetailPage.tsx` and `web/src/features/players/players.test.tsx`
  - F-29 player insights and off-season availability placement.
- `web/src/features/managers/ManagerProfilePage.tsx` and
  `web/src/features/managers/ManagerProfilePage.test.tsx` - F-08/F-09 trophy redesign and manager
  insight.
- `web/src/features/standings/StandingsPage.tsx` and
  `web/src/features/standings/StandingsPage.test.tsx` - F-03 standings insight.
- `web/src/features/matchups/BoxScorePage.tsx` and `web/src/features/matchups/matchups.test.tsx`
  - F-18 richer player breakdown.
- `web/src/features/draft/DraftPage.tsx` and `web/src/features/draft/DraftPage.test.tsx` - F-38
  drillable draft-value space.
- `web/src/features/records/RecordsPage.tsx` and `web/src/features/records/RecordsPage.test.tsx`
  - F-21 league trophy case and expanded records presentation.
- `web/src/features/power/PowerPage.tsx` and `web/src/features/power/PowerPage.test.tsx` - F-41
  revised methodology copy and fields.
- `web/src/design-system/index.tsx` only if the pages need a reusable compact insight/list
  primitive.

Backend targets if the current API cannot support the insight honestly:

- `src/ff_dashboard/analytics/standings.py`, `src/ff_dashboard/api/routes/standings.py`,
  `src/ff_dashboard/api/schemas.py` - standings luck/all-play insight.
- `src/ff_dashboard/analytics/owners.py`, `src/ff_dashboard/api/routes/owners.py`,
  `src/ff_dashboard/api/schemas.py` - manager consistency insight.
- `src/ff_dashboard/analytics/players.py`, `src/ff_dashboard/api/routes/players.py`,
  `src/ff_dashboard/api/schemas.py` - player insight summary.
- `src/ff_dashboard/analytics/matchups.py`, `src/ff_dashboard/api/routes/matchups.py`,
  `src/ff_dashboard/api/schemas.py` - box-score player enrichment.
- `src/ff_dashboard/analytics/power.py`, `src/ff_dashboard/api/routes/power.py`,
  `src/ff_dashboard/api/schemas.py` - revised power model fields.
- Tests: `tests/test_p9_power_unit.py`, `tests/test_p5_matchups_unit.py`,
  `tests/test_fixp1_owners.py`, plus new focused tests if new endpoint names do not fit an
  existing file.
- Docs after BUILD: update `docs/04_ANALYTICS_MODEL.md`, `docs/05_API_CONTRACT.md`, and
  `docs/07_PAGES_AND_VIEWS.md` for any shipped helper, endpoint, field, or page composition.

## Shared frontend helper

`deriveSeasonPhase(args): SeasonPhase`

Inputs:

- `current`: current season from `SeasonContext`.
- `seasons`: season list from `SeasonContext`.
- `now?: Date`, injected in tests.

Output:

- `phase`: `"offseason" | "inseason"`.
- `currentSeason`: selected current season.
- `lastCompletedSeason`: latest scored season before an unscored current season, otherwise the
  latest scored season.
- `reason`: short stable string for tests and copy.

Rules:

- Prefer data-driven scored coverage: an unscored current season with at least one prior scored
  season is off-season/pre-week-1.
- Treat a scored current season as in-season.
- Do not trust `seasons.status` until F-52 is fixed upstream.
- Do not hardcode a scored-era year.

## Backend metrics and endpoints

### F-03 standings insight

Metric: `standings_insights(session: Session, season_id: int, through_week: int | None = None) -> dict[str, Any]`

Endpoint: `GET /v1/seasons/{season_id}/standings/insights`

Schema: `StandingsInsights`

Shape:

- `available: bool`
- `reason: str | None`
- `teams: list[StandingsInsightTeam]`
- Each team carries `team_id`, `owner_id`, `owner_name`, `team_name`, `actual_wins`,
  `all_play_win_pct`, `expected_wins`, `luck_delta`, `points_for_rank`, `standings_rank`.

Known-answer tests:

- Fixture season where one team has fewer actual wins than its all-play profile expects.
- Gap case for a season/week with no completed scored matchups: `available:false`, no fake zeros.
- `through_week` caps both actual and all-play calculations.

### F-09 manager insight

Metric: `owner_consistency(session: Session, owner_id: int) -> dict[str, Any] | None`

Endpoint: add `consistency` to `GET /v1/owners/{owner_id}`.

Schema: `OwnerConsistency`

Shape:

- `available: bool`
- `reason: str | None`
- `weekly_points_stdev: float | None`
- `rank_among_owners: int | None`
- `best_season_year: int | None`
- `best_season_points_for: float | None`
- `signature`: stable label such as `"steady scorer"` or `"boom/bust"`.

Known-answer tests:

- Fixture owner with multiple weekly scores ranks as more/less consistent than another owner.
- Owner with no scored team weeks returns `available:false`.

### F-29 player insight

Metric: `player_insights(session: Session, player_id: int) -> dict[str, Any] | None`

Endpoint: `GET /v1/players/{player_id}/insights`

Schema: `PlayerInsights`

Shape:

- `available: bool`
- `reason: str | None`
- `best_week`, `best_season`, `league_roster_span`, and `most_rostered_by` where derivable.

Known-answer tests:

- League-relevant player with scoring and ownership returns best week/season and roster span.
- Player with ownership but no scoring returns ownership insight plus a scored-data gap for scoring
  fields.
- Unknown player returns the existing not-found behavior.

### F-18 box-score breakdown

Metric: extend existing box-score row assembly in `analytics/matchups.py`; no new endpoint.

New schema fields on each box-score player if needed:

- `team_point_share: float | None`
- `projection_delta: float | None`
- `lineup_value: "starter_hit" | "starter_miss" | "bench_pop" | "neutral" | None`

Known-answer tests:

- Starter share is computed from the authoritative team total and is null when the team total is
  missing.
- Projection delta is null when projection is absent, not `0`.
- Bench player who would have improved the lineup gets `bench_pop`.

### F-41 power model

Metric: keep the existing `power_ranking(session, season_id, through_week=None)` surface, but revise
the model to team-level inputs only:

```text
power_score = 0.40 * z(points_for_per_game)
            + 0.25 * z(all_play_win_pct)
            + 0.20 * z(win_pct)
            + 0.15 * z(recent_points_for_per_game)
```

Schema additions:

- `all_play_win_pct`
- `z_all_play_win_pct`
- updated `weights`
- updated `definition`/methodology copy.

Known-answer tests:

- Tiny fixture with two weeks proves all-play ranking independent of schedule luck.
- Pre-2016/team-total-only season can compute because no player-level scoring is needed.
- No scored/completed team games returns `available:false`.

## View composition

### F-01 home

- Drop scored-era count, latest-player-leader callout, and power top movers.
- Always show fuller standings context and an expanded records strip.
- Off-season: show last completed season finish/champion module, top season scorers from the last
  scored season, and recent activity if a proven activity source exists; otherwise show a small
  `DataGap` for activity rather than synthesizing a feed.
- In-season: show current week matchups, current week top scorers, and recent in-season activity
  where available.

### F-29 player detail

- In off-season, move availability below the player insight module or collapse it behind a compact
  "current-season only" affordance.
- In-season, keep availability visible.
- The new player insight module should lead with best week/best season/league ownership facts from
  the backend insight endpoint.

### F-08 and F-09 manager profile

- Replace the awkward trophy list with a compact hardware rail: titles, runner-up/podium finishes,
  and year/team pills.
- Add manager consistency insight from the backend. Do not derive stdev/ranks in the component.

### F-18 box score

- Keep the existing expandable per-player breakdown, but add contribution share, projection delta,
  and lineup-value labels when fields are present.
- Preserve zero-point explanations and existing DataGap behavior.

### F-21 records

- Add a league-wide trophy case using `/v1/records/championships`.
- Include search/filter over manager/year/result labels in the records section.
- Keep per-manager trophy case distinct from the records league trophy case.

### F-38 draft

- Add position and round filters/sorts for the pick-value table.
- Add click-through/drill-down state for steal/bust cards that focuses the corresponding pick in
  the value table or draft grid.
- Do not recalculate value in the frontend; use the existing `value` field.

### F-41 power

- Keep the power page, update methodology copy to explain all-play schedule-luck resistance, and
  show each component.
- Remove power top-movers from home only.

## Test plan

BUILD iteration:

- Backend: run the one changed file at a time, e.g. `uv run pytest tests/test_p9_power_unit.py -q`
  or the new endpoint/unit file.
- Frontend: run focused vitest files for changed pages, e.g.
  `npm run test -- PowerPage.test.tsx DraftPage.test.tsx`.
- API contract: after backend schema changes, run `npm run gen:api` in `web/` and check generated
  client drift. Expected drift is limited to new P6 fields/endpoints.

VERIFY:

- Backend full gate: pytest, ruff, mypy, forbidden write/import grep.
- Frontend full gate: `npm run gen:api` + drift check, typecheck, lint if script exists, vitest.
- Browser click-through on real DB: home off-season composition, player detail off-season insight,
  manager profile trophy/consistency, standings insight, records trophy case, draft filters and
  drill-down, scored box score expansion, and power methodology/components.
