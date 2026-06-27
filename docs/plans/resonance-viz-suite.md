# Plan — Resonance viz suite (builds #2–#7)

Charter: `docs/PHASE2_5_RESONANCE.md`. Follows build #1 (Legacy-Spine,
`resonance-legacy-spine.md`). This plans the rest of the data-viz I suggested, each as a
self-contained BUILD session. Every chart reuses the leg's marker grammar (gold = champion,
red = Sacko, honest gaps) and the `ChartFrame`/`DataTable` accessibility wrapper.

**Key grounding (verified against the live BFF):** more of this exists than expected.
- `/v1/seasons/{id}/standings/insights` → `StandingsInsightTeam` already has `actual_wins`,
  `expected_wins`, `all_play_win_pct`, `luck_delta` (= actual − expected: **negative = robbed /
  unlucky, positive = lucky**), plus `most_robbed` / `most_blessed`. **The xW/all-play keystone
  is already computed** — the StandingsPage already fetches it.
- `/v1/seasons/{id}/standings/timeline` → `TimelineTeam.points[] {week, rank, points_for}`
  (already feeds `RankFlow`).
- `/v1/teams` → all owners' per-season rows with `points_for` + `is_champion` + `is_sacko`.
- `/v1/teams/{id}/scoring-trend` → per-team weekly `team_score` vs `league_avg`.
- `/v1/owners/{a}/head-to-head/{b}` → `H2HMeeting {season_year, week, matchup_id, margin_for_a}`
  for closest/lopsided/highest, but **not** the full meeting list (see build #6).

**Build order = ascending cost.** #2–#4 are pure-frontend (no `gen:api` drift); #5–#6 need a
small backend addition; #7 needs a new analytics module.

---

## Build #2 — Luck bars (Expected Wins) · pure frontend ★ recommended next

**What:** a zero-centered **diverging bar** per team for a season — `luck_delta` (actual −
expected wins). Left/cool = **robbed** (won fewer than they deserved), right/gold = **lucky**
(won more). Annotate `most_robbed` 😤 and `most_blessed` 🍀. The most beloved "hidden truth" in
fantasy, and it's the league's own people. *Reckon.*

**Why no backend:** `/v1/seasons/{id}/standings/insights` already returns `luck_delta`,
`actual_wins`, `expected_wins`, `all_play_win_pct` per team + the two extremes. The StandingsPage
already fetches this payload.

**Files:**
- `web/src/charts/index.tsx` — new `DivergingBars` primitive: a horizontal `BarChart`, a
  `ReferenceLine x={0}`, per-bar fill by sign (gold positive / steel-blue negative), value labels,
  the standard `ChartFrame` + `DataTable` fallback. Reusable for any signed metric later.
- `web/src/features/standings/StandingsPage.tsx` — add a "Luck" card/section under the insights
  the page already loads (near the power lens). A subtitle explains xW in one sentence + links to
  an explainer.
- Optional: a Viz-Lab exhibit (season picker) — cheap, and keeps the Lab growing.

**Signature:**
```ts
function DivergingBars(props: {
  data: { label: string; value: number; note?: string; tone?: "pos" | "neg" }[];
  title: string;
  xLabel?: string;
  height?: number;
}): React.ReactElement
```

**Tests:** `DivergingBars` renders figure + data-table; positive and negative bars carry distinct
fills; a zero value sits on the reference line (no crash). StandingsPage: the Luck section renders
`most_robbed`/`most_blessed`, and shows the insights `DataGap` when `available:false`.

**Done when:** Standings shows per-team luck bars for a season with the two extremes called out;
honest gap when insights unavailable; FE typecheck + test green; no `gen:api` drift.

---

## Build #3 — Rank-race upgrade · pure frontend

**What:** elevate the existing `RankFlow` bump chart into a broadcast-grade season race —
**champion line ends in a gold node, Sacko line in 💩**, a one-shot intro animation, and emphasis
on hover. Deploy on the Standings timeline (and reuse in a future Season Story page). *Reveal.*

**Why no backend:** `/standings/timeline` already gives per-week rank per team; final
champion/Sacko come from the season standings flags (`is_champion`/`is_sacko`, already on the
standings rows the page loads).

**Files:**
- `web/src/charts/index.tsx` — extend `RankFlow` (or a thin `RankRace` variant) to accept an
  optional per-series `marker: "champion" | "sacko" | null` and draw the end-node accordingly;
  gate a one-shot animation behind a prop (default off to keep other call sites/tests stable and
  visual-regression-friendly).
- `web/src/lib/rankflow.ts` — thread the champion/Sacko flag through `toRankFlow`.
- `web/src/features/standings/StandingsPage.tsx` — pass the markers; keep the existing usage working.

**Tests:** the upgraded chart still renders the data-table fallback; a series flagged champion
exposes the gold end-marker (`<title>`), Sacko the 💩; animation prop defaults off.

**Done when:** the standings race shows gold/💩 terminals on the right lines; existing RankFlow
callers unaffected; FE gate green.

---

## Build #4 — Dynasty / title streamgraph · pure frontend

**What:** a stacked-area / streamgraph of **cumulative league points by manager across seasons**,
with championship seasons marked — the "who has quietly piled up the most, and when did dynasties
run" view. A companion compact "title-share ribbon" (who held the title each year) reads as the
league's ages. *Relive.*

**Why no backend:** `/v1/teams` (`TeamsIndex`) carries every owner's per-season `points_for` +
`is_champion` + `is_sacko`; cumulative sums and title runs are pure presentation reshaping.

**Files:**
- `web/src/charts/index.tsx` — new `StreamArea` primitive (Recharts stacked `Area`), theme-bound,
  with the `ChartFrame`/`DataTable` fallback. Champion seasons get a marker via a custom dot.
- `web/src/lib/` — a small reshaper (owners × seasons → cumulative rows), mirroring `rankflow.ts`.
- Home a candidate host later; for now a Viz-Lab exhibit + a section on the **Timeline** page
  (its natural home — eras/dynasties).

**Tests:** `StreamArea` renders figure + data-table; cumulative values are monotonic per series;
a season with no data is a gap, not 0.

**Done when:** the streamgraph renders cumulative points by manager with title markers; lands in
the Lab and/or Timeline; FE gate green.

---

## Build #5 — Weekly scoring beeswarm + intensity heatmap · small backend

**What:** (a) a **beeswarm/strip** of every team's weekly scores in a season — boom/bust vs steady
at a glance; (b) the same data as a **team × week intensity heatmap** (reusing the `Heatmap`
primitive). The fantasy-native "who's volatile" picture, on real league weeks. *Reveal.*

**Why a small backend:** no endpoint returns a season-wide team×week score matrix. `scoring-trend`
is per-team (would be N calls). Add one read-only aggregation endpoint.

**Backend (additive, read-only):**
- `analytics/` — `weekly_scores(session, season_id)` → per (team, week) `team_score` (reuse the
  matchup/score reads the box score already uses). Pure rows → numbers; unit-test against the
  fixture DB known answers.
- `api/schemas.py` — `SeasonWeeklyScores { season_id, season_year, regular_season_weeks, teams: [{team_id, owner_name, scores: [{week, score|null}]}] }`.
- `api/routes/seasons.py` — `GET /v1/seasons/{id}/weekly-scores`. Then `npm run gen:api`.

**Frontend:**
- `web/src/charts/index.tsx` — new `Beeswarm` primitive (a 1-D strip per series; deterministic
  jitter), theme-bound + data-table fallback.
- Reuse `Heatmap` for the intensity grid.
- Host: a Viz-Lab exhibit first; natural home is a season view / Stats.

**Tests:** analytics unit test (known weekly scores); contract test for the endpoint + gap
behavior (unscored season → `available:false`); `Beeswarm` component test (figure + fallback;
null week = gap).

**Done when:** beeswarm + intensity heatmap render for a scored season, honest gap for an unscored
one; backend pytest/ruff/mypy + FE gate green; `gen:api` regenerated and committed.

---

## Build #6 — Annotated rivalry margin line · small backend

**What:** for any pair, a line of **signed margin across every meeting over time**, with the famous
games pinned (the blowout, the nail-biter, playoff meetings) and deep-links to those box scores.
The "shape of a rivalry." *Relive / Reckon.* Lands on the existing Pairwise page.

**Why a small backend:** `HeadToHead` exposes only closest/lopsided/highest meetings, not the full
ordered list needed for a line.

**Backend (additive):**
- `analytics/head_to_head.py` `pairwise_record` — add `meetings: list[H2HMeeting]` (every meeting,
  chronological, `margin_for_a` already defined on `H2HMeeting`). Mark `is_playoff` per meeting if
  cheap.
- `api/schemas.py` — add `meetings: list[H2HMeeting] = []` to `HeadToHead` (already `extra=allow`,
  so additive). `npm run gen:api`.

**Frontend:**
- `web/src/charts/index.tsx` — `AnnotatedLine` (extend `LineTrend`): a zero reference line, signed
  fill above/below, optional pinned annotations with deep-links.
- `web/src/features/rivalries/PairwisePage.tsx` — render it from the new `meetings`.

**Tests:** analytics test (meetings list ordered, signed margins correct); `AnnotatedLine`
component test; PairwisePage shows the line + a deep-link to a pinned game.

**Done when:** a pairwise page draws the margin-over-time line with pinned famous games linking to
box scores; backend + FE gate green; client regenerated.

---

## Build #7 — Manager efficiency ("Lineup IQ") scatter · new analytics

**What:** a value-style scatter — **% of optimal points captured** (x) vs **scoring** (y) per
manager (or season), quadrant-labelled (sharp managers, point-rich but leaky, etc.). The
fantasy-native "manager skill" signal, on the league's own people. *Reckon.* Reuses
`ScatterQuadrant`.

**Why new analytics:** optimal lineup is computed per box score in `analytics/matchups.py`, but
there is no season/career aggregate of optimal-vs-actual. This is the one build here that needs a
real new metric (and the most care).

**Backend:**
- `analytics/efficiency.py` — aggregate captured/optimal across a manager's started lineups
  (reuse the existing optimal-lineup solver); emit `efficiency_pct`, `points_for`, sample size,
  and the honest gap for unscored seasons. Thorough unit tests vs the fixture DB.
- endpoint + schema (`/v1/owners/efficiency` or season-scoped); `gen:api`.

**Frontend:** reuse `ScatterQuadrant` (already built) — map efficiency→x, scoring→y, tone by
quadrant; host in the Lab, natural home a Managers comparison.

**Done when:** efficiency metric is unit-tested against known answers; the scatter renders with its
"how this is computed" explainer; gaps honest; full gate green.

---

## Not a standalone chart (noted, not planned here)

- **Small multiples / season-recap grid** — that's the layout of the **Season Story page** (a
  narrative build), not a reusable chart primitive. It composes #2–#4 once those land. Plan it with
  the Season Story page, per the charter.
- **Career luck aggregate** (all-time xW − actual across a manager's seasons) — a natural backend
  follow-up to #2 once per-season luck ships; small.
