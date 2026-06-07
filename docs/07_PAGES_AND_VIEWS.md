# 07 — Pages & Views

The screen-by-screen information architecture. Each view lists what it shows, which API
endpoints feed it, which charts/components it uses, and the data-gap behavior. Routes are
deep-linkable (N3 / F10.2). This is the map a builder follows to compose pages from the
design-system primitives.

**Route convention (as built).** Season-scoped views are driven by the **global season
switcher**, so their routes are flat (`/standings`, `/power`, `/matchups`, `/draft`) rather
than carrying a `/seasons/{season_id}/...` prefix — the selected season lives in app state, not
the path. Entity routes that *are* path-scoped (`/matchups/{matchup_id}`, `/teams/{team_id}`,
`/players/{player_id}`, `/rivalries/{a}/vs/{b}`) stay deep-linkable. (This is a deliberate
departure from the originally-sketched season-in-URL scheme.)

---

## Home — Command Center  `/`

The landing view; a glanceable cockpit for the current season.

- **Shows:** standings snippet (top 4 / bottom 4), the power ranking, and the records book —
  arranged as a cockpit.
- **Endpoints:** composed **client-side** from `GET /v1/seasons/{id}/standings`,
  `GET /v1/records`, and `GET /v1/seasons/{id}/power` (there is no `/v1/home` composite; the
  page orchestrates, it does no math).
- **Components/charts:** `StatGrid`, `Card`, `Table` (mini standings), `RankFlow` thumbnail.
- **Gaps:** pre-week-1 → `EmptyState` ("season hasn't started"); current season not yet
  scored → power ranking shows `DataGap`.

## Standings  `/standings`

- **Shows:** full standings table (rank, manager/team, W-L-T, PF, PA, completed-season
  finish, streak); a standings-over-time chart with rank-ordered Week N tooltips.
- **Endpoints:** `/v1/seasons/{id}/standings?through_week=`,
  `/v1/seasons/{id}/standings/timeline`.
- **Components/charts:** `Table`, `RankFlow`, `RecordLine`, `Trophy`.
- **Gaps:** historical standings exist for 2010–2025 → render normally; if season metadata is
  pending, `DataGap`.

## Power ranking  `/power`

- **Shows:** the current power ranking (with each team's components and the model weights), an
  "how this is computed" explainer, and a power-score-over-time chart.
- **Endpoints:** `/v1/seasons/{id}/power?through_week=`, `/v1/seasons/{id}/power/timeline`.
- **Components/charts:** `Table`, `RankFlow`/`LineTrend`, `Tabs`.
- **Gaps:** current season not yet scored → `DataGap`.

## Playoffs / Bracket  *(not built)*

- **Planned route:** `/bracket` · **planned endpoint:** `/v1/seasons/{id}/bracket`.
- **Status:** specified (F2.3) but **not implemented** — neither the route nor the endpoint
  exists yet. Champion/runner-up/last-place are surfaced today via the season summary and the
  records book. If built, it must show the "post-regular-season weeks, not a proven
  championship-vs-consolation bracket" caveat badge. Tracked in `10_OPEN_QUESTIONS.md`.

## Matchups (week view)  `/matchups`

- **Shows:** all matchups for the (switcher-selected season, week) as cards (both teams,
  scores, win/loss, signed margin per side); a `WeekStepper` with prev/next and direct week select.
- **Endpoint:** `/v1/seasons/{id}/weeks/{week}/matchups`.
- **Components:** matchup cards, `BarCompare` (optional per-card mini bar), `Badge`.

## Box Score  `/matchups/{matchup_id}`

- **Shows:** both lineups side by side; per-player league points + breakdown; bench points;
  optimal lineup and "points left on the bench"; projection vs actual per starter.
- **Endpoint:** `/v1/matchups/{matchup_id}/box-score`.
- **Components/charts:** two-column lineup tables, `StackedBreakdown` per expandable player
  row, `Stat` for totals/bench/left-on-bench.
- **Gaps:** a DST slot whose row is genuinely missing → `DataGap` "team defense not scored"
  (DST is otherwise scored end-to-end); per-player scoring and breakdowns now exist for 2010–2025
  since F-51; only an unscored current/in-progress season should show the season-unscored
  affordance, driven by `is_scored`.

## Team  `/teams/{team_id}`

- **Shows:** season summary (record, rank, owner) with season navigation across the manager's
  teams; roster by week (with `WeekStepper`);
  schedule with results; scoring trend vs league average; two distinct activity spaces —
  **"Draft"** (recorded transactions, draft-only on the real DB) and **"In-season moves"**
  (derived add/drop/retain from week-over-week roster diffs). A season with <2 roster
  snapshots renders the `roster_history_unavailable` `DataGap`, never a fake "no moves".
- **Endpoints:** `/v1/teams/{id}`, `/v1/teams/{id}/roster?week=`,
  `/v1/teams/{id}/schedule`, `/v1/teams/{id}/scoring-trend`, `/v1/teams/{id}/transactions`,
  `/v1/teams/{id}/roster-moves`, `/v1/owners/{owner_id}/seasons`.
- **Components/charts:** `StatGrid`, roster `Table`, schedule list, `LineTrend`, action `Pill`s.

## Managers (index)  `/managers`

- **Shows:** league-wide career leaderboard — a "league legends" strip (most titles, best
  win %, most points, most seasons) over a sortable career table (manager, seasons, win %,
  record, points for, titles, best/avg finish). Each row deep-links to the manager profile.
- **Endpoint:** `/v1/owners` (built + tested).
- **Sort/derive:** default order is the BFF's (titles → wins → PF); columns toggle asc/desc
  client-side. Win % is derived in-component over decided games — managers with no games on
  record show `—`, never a fake 0 %.

## Manager profile  `/managers/{owner_id}`

- **Shows:** career aggregate header (seasons, W-L-T, win %, PF, best finish, titles) with a
  latest-roster link when the manager has season/team history;
  trophy case (championships + podium finishes); career trajectory chart (final finish by
  season, `RankFlow`); season-by-season record table; rivalry snapshot ("owns" / "owned by"
  splits deep-linking to the pairwise pages, games labelled as `N GP`).
- **Endpoints:** `/v1/owners/{id}`, `/v1/owners/{id}/seasons`, `/v1/owners/{id}/trajectory`,
  `/v1/owners/rivalry-matrix` (all built + tested).
- **Gaps:** record-only (pre-coverage) seasons return 0 PF and render a `DataGap` in the
  points-for column rather than a `0`. A missing owner id renders a not-found state.

## Rivalries  `/rivalries`  and  `/rivalries/{a}/vs/{b}`

- **Matrix view:** the full N×N win-pct heatmap; click a cell → the pairwise page.
  - **Endpoint:** `/v1/owners/rivalry-matrix`; **chart:** `Heatmap`.
- **Pairwise view:** all-time record, average margin, highest-scoring meeting, most lopsided
  meeting, playoff meetings; a timeline of their games.
  - **Endpoint:** `/v1/owners/{a}/head-to-head/{b}`; **components:** `StatGrid`, game list.
- This is a high-emotional-value view for a 16-season league — prioritize it (it's in the
  early roadmap).

## Records book  `/records`

- **Shows:** the superlatives (highest/lowest team score, biggest blowout, narrowest win,
  highest-scoring matchup, best player week, longest streaks, most titles, etc.), each as a
  `Card` with the value and a deep-link to its source matchup/player/season; championship
  history / dynasty timeline; best/worst draft picks ever.
- **Endpoints:** `/v1/records`, `/v1/records/championships`, `/v1/records/draft`.
- **Components:** record `Card`s, `Trophy`, dynasty `LineTrend`/timeline.
- **Gaps:** player records use the scored player window (now 2010–2025); team-record
  superlatives use `team_record_era`, and record-only superlatives (titles) note their broader
  range.

## Players (index)  `/players`

- **Shows:** searchable/filterable league-relevant player index (name, position, NFL team,
  active, rostered-season span). It does not expose a public all-player scope or a scored flag.
- **Endpoint:** `/v1/players?...`.
- **Components:** search bar, filter chips, paginated `Table` + `PlayerChip`.

## Player detail  `/players/{player_id}`

- **Shows:** metadata + cross-platform IDs; weekly scoring history chart (per season);
  compact ownership cards within the league; projections; current-season availability.
- **Endpoints:** `/v1/players/{id}`, `/v1/players/{id}/scoring?season=`,
  `/v1/players/{id}/ownership`, `/v1/players/{id}/availability?season=`.
- **Components/charts:** `LineTrend`/`BarCompare` (weekly scoring), ownership cards,
  availability strip.
- **Gaps:** availability for non-current seasons → `DataGap`.

## Stats explorer  `/stats`

- **Shows:** season totals by default, with top scorers/weekly leaders still reachable by tab;
  position filters and jump-off links to player detail.
- **Endpoints:** `/v1/stats/top-scorers?...`, `/v1/stats/season-totals?...`.
- **Components:** filter bar, `Table`.

## Draft  `/draft`

- **Shows:** draft board as a horizontal 12-column snake grid; pick-value analysis
  (steals/busts) with a by-pick chart.
- **Endpoints:** `/v1/seasons/{id}/draft`, `/v1/seasons/{id}/draft/value`.
- **Components/charts:** draft grid, `BarCompare` (value by pick), `PlayerChip`.
- **Gaps:** seasons without captured drafts → `DataGap`.

## Coverage / About  `/about`

- **Shows:** the data coverage panel (what's scored, reconstruction status, known gaps), data
  provenance, and attribution (nflverse CC-BY, Sleeper) — satisfies Phase 1's attribution
  obligation in the UI.
- **Endpoint:** `/v1/meta`.

---

## Build priority (which views ship first)

Anticipating the most-used and highest-value views, and respecting data readiness:

1. **App shell + Home + Standings + Box score + Manager profile** — the daily-driver core.
2. **Rivalries + Records book** — the emotional core of a long-running league; high reuse of
   primitives.
3. **Players + Stats explorer + Team page** — exploration depth.
4. **Draft + Power + Coverage/About + global search + polish passes.**

> **As-built note:** all of the above ship, including the Manager index/profile pages (#1),
> which are now composed against their ready backend (`feature/managers-page`). The
> Playoffs/Bracket view (above) was never built. Everything else is additive composition of the
> same primitives + one endpoint each, as designed.
