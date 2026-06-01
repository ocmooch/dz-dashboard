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

- **Shows:** full standings table (rank, manager/team, W-L-T, PF, PA, streak); a
  standings-over-time chart; a "through week" stepper for time-travel.
- **Endpoints:** `/v1/seasons/{id}/standings?through_week=`,
  `/v1/seasons/{id}/standings/timeline`.
- **Components/charts:** `Table` (sortable), `RankFlow`, `WeekStepper`, `RecordLine`.
- **Gaps:** 2010–2015 standings exist (record-only) → render normally; if season metadata is
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
  scores, win/loss, margin); a `WeekStepper`.
- **Endpoint:** `/v1/seasons/{id}/weeks/{week}/matchups`.
- **Components:** matchup cards, `BarCompare` (optional per-card mini bar), `Badge`.

## Box Score  `/matchups/{matchup_id}`

- **Shows:** both lineups side by side; per-player league points + breakdown; bench points;
  optimal lineup and "points left on the bench"; projection vs actual per starter.
- **Endpoint:** `/v1/matchups/{matchup_id}/box-score`.
- **Components/charts:** two-column lineup tables, `StackedBreakdown` per expandable player
  row, `Stat` for totals/bench/left-on-bench.
- **Gaps:** DST slots → `DataGap` "team defense not scored"; pre-2016 → breakdowns absent,
  show captured points only with a note.

## Team  `/teams/{team_id}`

- **Shows:** season summary (record, rank, owner); roster by week (with `WeekStepper`);
  schedule with results; scoring trend vs league average; the season's transactions.
- **Endpoints:** `/v1/teams/{id}`, `/v1/teams/{id}/roster?week=`,
  `/v1/teams/{id}/schedule`, `/v1/teams/{id}/scoring-trend`, `/v1/teams/{id}/transactions`.
- **Components/charts:** `StatGrid`, roster `Table`, schedule list, `LineTrend`.

## Managers (index)  `/managers`  *(placeholder — not built)*

- **Shows (planned):** every manager with a career line (record, championships, best finish).
- **Endpoint:** `/v1/owners` (built + tested).
- **Status:** the route renders a `PlaceholderPage`; the SPA view hasn't been composed yet
  even though the backend is ready. Tracked in `10_OPEN_QUESTIONS.md`.

## Manager profile  `/managers/{owner_id}`  *(placeholder — not built)*

- **Shows (planned):** career aggregate header (seasons, W-L-T, PF, titles, avg finish);
  trophy case; season-by-season record table; career trajectory chart; consistency percentile.
- **Endpoints:** `/v1/owners/{id}`, `/v1/owners/{id}/seasons`, `/v1/owners/{id}/trajectory`
  (all built + tested).
- **Status:** the route renders a `PlaceholderPage` — the highest-value unbuilt view. The
  pairwise rivalry page (below) currently carries the owner-vs-owner story. Tracked in
  `10_OPEN_QUESTIONS.md`.

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
- **Gaps:** scored-era records labeled "2016–2025"; record-only superlatives (titles) note
  their broader range.

## Players (index)  `/players`

- **Shows:** searchable/filterable player index (name, position, NFL team, active).
- **Endpoint:** `/v1/players?...`.
- **Components:** search bar, filter chips, paginated `Table` + `PlayerChip`.

## Player detail  `/players/{player_id}`

- **Shows:** metadata + cross-platform IDs; weekly scoring history chart (per season);
  ownership timeline within the league; projections; current-season availability.
- **Endpoints:** `/v1/players/{id}`, `/v1/players/{id}/scoring?season=`,
  `/v1/players/{id}/ownership`, `/v1/players/{id}/availability?season=`.
- **Components/charts:** `LineTrend`/`BarCompare` (weekly scoring), ownership timeline,
  availability strip.
- **Gaps:** availability for non-current seasons → `DataGap`.

## Stats explorer  `/stats`

- **Shows:** top scorers and season totals by position, sortable/filterable; jump-off to
  player detail.
- **Endpoints:** `/v1/stats/top-scorers?...`, `/v1/stats/season-totals?...`.
- **Components:** filter bar, `Table`.

## Draft  `/draft`

- **Shows:** draft board (round × team grid); pick-value analysis (steals/busts) with a
  by-round chart.
- **Endpoints:** `/v1/seasons/{id}/draft`, `/v1/seasons/{id}/draft/value`.
- **Components/charts:** draft grid `Table`, `BarCompare` (value by round), `PlayerChip`.
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

> **As-built note:** all of the above ship **except the Manager index/profile pages** (#1),
> which remain `PlaceholderPage` stubs despite their ready backend — the one outstanding gap
> against this plan. The Playoffs/Bracket view (above) was also never built. Everything else is
> additive composition of the same primitives + one endpoint each, as designed.
