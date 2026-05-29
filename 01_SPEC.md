# 01 — Specification

## Purpose

Phase 2 is the **human interface** to the Phase 1 data foundation. Phase 1 made every
league, team, player, and scoring fact queryable and accurate. Phase 2 makes it
*explorable and legible*: a fast, good-looking web app that turns 16 seasons of history
plus the live season into navigable views and visual insight. It computes the derived
metrics Phase 1 deliberately left out, and presents them.

Phase 2 is **read-only with respect to league data**. It never writes to the database, never
writes to NFL.com, and never runs the pipeline. It consumes; it does not mutate.

## System shape (one line)

`SQLite (Phase 1) → ff_dashboard analytics service (Python BFF) → HTTP/JSON → React SPA → you`

## Functional requirements

### F1. Command center (league home)

- **F1.1** A landing view summarizing the current season at a glance: current standings
  (top + bottom), this week's matchups with live/most-recent scores, the current power
  ranking, and a recent-activity feed (transactions, notable performances).
- **F1.2** A persistent season switcher so any view can be re-pointed at a historical year.
- **F1.3** Empty/degraded states when the current season hasn't started or a metric can't be
  computed (e.g., pre-week-1).

### F2. Standings & playoff picture

- **F2.1** Full standings for any season: W-L-T, points for/against, streak, rank.
- **F2.2** Standings *as of* any week (time-travel) and standings-over-time as a chart.
- **F2.3** Playoff bracket / final results for completed seasons; live playoff picture
  (who's in, who's on the bubble) for the current season where derivable.

### F3. Matchups & box scores

- **F3.1** All matchups for a given (season, week), each showing both teams and scores.
- **F3.2** A full box score for any matchup: both lineups, per-player league points, and the
  per-player scoring **breakdown** (passing/rushing/receiving/bonus/…), visualized.
- **F3.3** Bench points, optimal-lineup comparison ("points left on the bench"), and
  projection-vs-actual per player where projection data exists.

### F4. Teams

- **F4.1** A team page for any (season, team): final record/rank, roster by week, schedule
  with results, and the season's transactions.
- **F4.2** A season scoring trajectory chart (points per week vs league average).

### F5. Owners / managers (the persistent identity)

- **F5.1** A manager profile spanning all seasons: career W-L-T, points, best/worst
  finishes, championships, a trophy case.
- **F5.2** Season-by-season record table and a career trajectory chart.
- **F5.3** Manager-vs-field metrics (e.g., all-time scoring rank, consistency).

### F6. Head-to-head & rivalries

- **F6.1** All-time record between any two managers across every season they overlapped:
  total wins/losses, average margin, highest-scoring meeting, playoff meetings.
- **F6.2** A rivalry matrix (every manager vs every manager) as a heatmap.

### F7. Records book / hall of fame

- **F7.1** League records: highest/lowest team score ever, biggest blowout, narrowest win,
  highest-scoring matchup, best single-player week, longest win/loss streaks.
- **F7.2** Championship history and a dynasty timeline.
- **F7.3** Draft records: best and worst draft-pick value (points returned vs draft slot).

### F8. Players

- **F8.1** Searchable player index (by name, position, NFL team, active flag).
- **F8.2** Player detail: cross-platform IDs, weekly scoring history (raw + league points)
  with a chart, ownership history within the league, projections, and — for the current
  season only — availability state (owned / free agent / on waivers).
- **F8.3** Top scorers and season totals by position, sortable and filterable.

### F9. Draft

- **F9.1** Draft board for any season (round-by-round picks, by team).
- **F9.2** Draft value analysis: points-per-pick, steals and busts, by round.

### F10. Cross-cutting UX

- **F10.1** Global search (jump to any owner, team, player, or season).
- **F10.2** Deep-linkable URLs for every view (shareable, back-button correct).
- **F10.3** Consistent loading, empty, and error states everywhere.
- **F10.4** Responsive layout: usable on a laptop primarily, gracefully degraded on mobile.

## Non-functional requirements

### N1. Performance

- **N1.1** Warm analytics API responses < 200ms for 95% of requests (single user, indexed
  SQLite, in-process reads).
- **N1.2** First contentful paint < 1.5s on a local dev build; route transitions feel
  instant (cached server state via the query layer).
- **N1.3** Expensive rollups (records book, rivalry matrix) are computed server-side and
  cached in-process with explicit invalidation tied to the latest `pipeline_runs` id.

### N2. Correctness & honesty about data

- **N2.1** Every number the dashboard shows must trace to a Phase 1 fact or a documented
  formula in `04_ANALYTICS_MODEL.md`. No silent fabrication.
- **N2.2** Known data gaps are surfaced in the UI, not hidden: unscored 2010–2015 seasons,
  current-season-only availability, and incomplete DST scoring render as explicit
  "not available" affordances, never as zeros masquerading as data.
- **N2.3** Every API response carries provenance (`meta`: data freshness + pipeline run id),
  matching the Phase 1 envelope convention.

### N3. Maintainability & durability

- **N3.1** The frontend holds **no business logic**. All derived metrics live in the BFF.
  If a number is wrong, there is exactly one place to fix it.
- **N3.2** Components are built as a small, documented design-system library first, then
  composed into pages — so later polish/addition is additive, not a rewrite.
- **N3.3** The frontend's API client is **generated from the BFF's OpenAPI schema**; the
  contract is the single source of truth and drift is caught at build time.
- **N3.4** No source-specific or schema-specific knowledge in the frontend; it knows only the
  analytics API.

### N4. Testability

- **N4.1** Every analytics metric has unit tests against a small fixture database with
  known, hand-verifiable answers.
- **N4.2** Every API endpoint has a contract test (shape + status codes) via FastAPI's
  TestClient, exactly as Phase 1 does.
- **N4.3** Key components have component tests; the critical user journeys have a small set
  of end-to-end tests.

### N5. Security & operation

- **N5.1** Both services bind to `127.0.0.1` by default. No internet exposure without an
  explicit, documented config change.
- **N5.2** No secrets in Phase 2. The BFF reads the database read-only; it never needs the
  NFL cookie. (If the frontend ever needs the Phase 1 pipeline's cookie status, it reads it
  via an existing Phase 1 status endpoint, never the secret itself.)
- **N5.3** One command brings the whole thing up for daily use; documented in operations.

### N6. Forward compatibility

- **N6.1** Adding a new view = a new route + a new analytics function + (optionally) a new
  endpoint. No changes to existing views required.
- **N6.2** The design system supports theming via CSS variables so the visual direction can
  be re-skinned without touching component logic.
- **N6.3** The analytics API is versioned (`/v1`); breaking changes mount a new prefix.

## Explicit non-goals for Phase 2

- ❌ **No predictions, recommendations, or AI advice.** That's Phase 3. Phase 2 shows what
  *happened* and *is*, not what *should* happen.
- ❌ **No writes** of any kind to league data or NFL.com.
- ❌ **No running the pipeline from the UI.** Ingestion stays in the Phase 1 CLI/cron.
- ❌ **No multi-user accounts, auth, or sharing infrastructure.** Single user, localhost.
- ❌ **No real-time in-game scoring.** Weekly granularity, matching Phase 1.
- ❌ **No reconstructing data Phase 1 doesn't have** (e.g., historical availability). The UI
  states the gap; it does not invent.
