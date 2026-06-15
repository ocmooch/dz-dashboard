# Plan — Rivalries page insights (filling the empty space below the matrix)

**Type:** post-roadmap product enhancement (not a P# milestone). P6 shipped the matrix +
pairwise pages; this fills the rest of `/rivalries` with league-wide rivalry insight bands.

**Audience/message contract (the lens this is built through):** the reader is a current or
former member of *this* league. Every band must earn a *"I never would've thought to check
that"* reaction — personal relevance × surprise × screenshot-ability — while obeying the
project's honesty rules (never render 0 for missing data; min-sample gates so a 1–0 pair
can't masquerade as a rivalry; all math in `analytics/`, tested).

---

## Scope

Keep the existing matrix card at the top of `RivalriesPage.tsx` untouched. Add five new
bands below it, fed by **one** new bundle endpoint. Four of the five are pure reducers over
data `all_pairwise()` already loads (per-meeting score, margin, week, season_year,
is_playoff); only the playoff-finals labelling reaches into `bracket.py`.

**Bands, in display order:**

1. **Hottest Rivalries (intensity leaderboard)** — the new centerpiece. A composite "heat"
   score ranks which rivalries matter most *right now*, with a one-line justification under
   each (record · last meeting · playoff count) so the rank is never a black box.
2. **The Record Book (league-wide superlatives)** — closest game ever, biggest beating,
   highest-scoring duel, most-played pairing, dead-even rivalry. Each deep-links to its
   source matchup.
3. **Active Dominations (streaks)** — longest consecutive H2H win run all-time, plus any
   *currently active* streaks ≥3 ("X has beaten Y six straight since 2021").
4. **Nemesis & Favorite Victim (per active manager)** — the "check your own row" magnet.
   For each of the 12 active managers: worst-record opponent and best-record opponent
   (min-sample gated), each row linking to the pairwise page.
5. **Playoff Rivalries (stakes)** — pairs ranked by postseason meetings, their playoff-only
   record, the most recent playoff meeting, and the finals/championship meeting when
   `bracket.py` can name one.

---

## Files to touch

**Backend**
- `src/ff_dashboard/analytics/rivalries.py` — **new** module. Imports `all_pairwise` from
  `head_to_head` (do not duplicate the dedupe/bye logic). Houses all five reducers.
- `src/ff_dashboard/analytics/head_to_head.py` — no change to existing fns. `closest_rivalry()`
  (already written, currently unused) gets reused by the record book.
- `src/ff_dashboard/api/schemas.py` — add `RivalryInsights` envelope + nested schemas.
- `src/ff_dashboard/api/routes/rivalries.py` — **new** router, one endpoint; register it in
  the app router include (confirm the include site in BUILD; mirror how `owners` router is wired).

**Frontend** (pure presentation)
- `web/src/features/rivalries/RivalriesPage.tsx` — add the five bands under the matrix card.
- `web/src/features/rivalries/components/` — **new** small presentational components
  (`IntensityLeaderboard`, `RecordBook`, `NemesisTable`, `StreakCallout`, `PlayoffRivalries`).
- `web/src/lib/queryKeys.ts` — add `rivalryInsights` key.
- `web/src/lib/api/*` — **regenerated only** via `npm run gen:api` (never hand-edit).

---

## Analytics signatures (`analytics/rivalries.py`)

All build on `all_pairwise(session) -> dict[Pair, agg]` where `agg["meetings"]` is the
per-game list. Tunable thresholds live as module constants:

```python
MIN_INTENSITY_GAMES = 4   # a pair needs a real history to rank as "hot"
MIN_NEMESIS_GAMES   = 3   # below this, a record isn't a rivalry
MIN_ACTIVE_STREAK   = 3   # surface active dominations of 3+

def rivalry_records(session) -> dict[str, Any]:
    """League-wide superlatives. Each item: {owner_a, owner_b, value, season_year,
    week, matchup_id, a_score?, b_score?} or available:false when no meetings exist.
    Items: closest_game (min |margin|), biggest_blowout (max |margin|),
    highest_scoring_duel (max a+b), most_played_pairing (max games),
    dead_even_rivalry (reuse head_to_head.closest_rivalry)."""

def rivalry_streaks(session) -> dict[str, Any]:
    """Per pair, order meetings by (season_year, week); compute the longest one-owner
    run and the current trailing run. Returns the record streak + active streaks
    >= MIN_ACTIVE_STREAK, each with owner names, length, span, last matchup_id."""

def rivalry_intensity(session, top_n=5) -> dict[str, Any]:
    """Composite heat per pair (>= MIN_INTENSITY_GAMES). Components, each 0..1:
      balance  = 1 - 2*|win_pct - 0.5|        # 1.0 at dead even
      volume   = min(games / VOL_CAP, 1)      # more meetings = hotter
      tightness= 1 - min(avg|margin| / MARGIN_CAP, 1)  # close games = hotter
      recency  = decay on seasons-since-last-meeting
      stakes   = min(playoff_meetings / STAKE_CAP, 1)
    heat = weighted sum -> 0..100. Return ranked top_n WITH the component breakdown
    and the justifying facts (record, last_meeting, playoff_meetings) — never opaque."""

def manager_nemeses(session) -> dict[str, Any]:
    """For each ACTIVE owner: nemesis (lowest win_pct opponent, >= MIN_NEMESIS_GAMES)
    and favorite_victim (highest win_pct opponent, same gate). Owners with no
    qualifying opponent return nulls (UI shows a quiet gap, not a zero)."""

def playoff_rivalries(session, top_n=6) -> dict[str, Any]:
    """Pairs with >=1 postseason meeting (filter meetings on is_playoff). Each:
    playoff record (recomputed from the playoff meetings only), most_recent playoff
    meeting (deep-link), and finals_meeting when bracket.season_bracket labels a
    championship game for that (season, pair). Ranked by playoff meeting count."""

def rivalry_insights(session) -> dict[str, Any]:
    """Bundle: {records, streaks, intensity, nemeses, playoffs}. Each sub-band carries
    its own available/reason so one empty band never blanks the page."""
```

**Honesty notes:** every superlative/streak/playoff item that resolves to a real game
carries a `matchup_id` for deep-linking. Min-sample gates are *constants*, documented, not
magic numbers. No band hardcodes a year; the playoff/streak windows are data-driven.

---

## API contract

- **Endpoint:** `GET /v1/rivalries/insights` → `Envelope[RivalryInsights]`.
- One request powers all five bands (mirrors the existing `/insights` bundle pattern used by
  standings/players). `meta` via `build_meta(session)` as usual.
- `RivalryInsights` schema = `{ records, streaks, intensity, nemeses, playoffs }`, each an
  optional/`available`-flagged sub-object. Add nested pydantic models; keep `extra="allow"`
  consistent with how `HeadToHead` widens (frontend reads the rich fields).
- Run `npm run gen:api` and commit the regenerated client; assert no drift in the gate.

---

## Frontend

`RivalriesPage.tsx`: keep the matrix `Card` first, then a `useQuery(qk.rivalryInsights)`.
Render the five bands in order (1 Intensity, 2 Record Book, 3 Streaks, 4 Nemesis, 5 Playoffs),
each its own `Card`/`CardHeader`. All presentation — no math, no thresholds in the UI.

- **IntensityLeaderboard** — ranked rows with a heat bar (reuse a token/`Badge`), names as
  `Chip`s, justification line, row → `/rivalries/{a}/vs/{b}`.
- **RecordBook** — superlative grid; each cell a `Stat` + deep-link to `/matchups/{id}`.
- **StreakCallout** — record streak + active-domination list.
- **NemesisTable** — 12 active managers; nemesis & victim columns; rows link to pairwise.
  Missing-opponent cells render `DataGap`, never "0".
- **PlayoffRivalries** — postseason record rows; finals badge when present.

Loading → `Skeleton`; error → `ErrorState` with retry; empty band → `DataGap`.

---

## Tests

**Backend — `tests/dashboard/test_rivalries.py`** (fixture DB, known answers):
- record book: each superlative returns the expected pair/value/matchup_id.
- intensity: ordering is deterministic; a pair below `MIN_INTENSITY_GAMES` is excluded;
  heat components are within [0,1] and the justification facts match the record.
- streaks: longest run and an active run computed correctly across a season boundary.
- nemeses: active-only; an owner whose only opponent is below the gate yields nulls.
- playoffs: playoff-only record differs from all-time where expected; finals labelled when
  the bracket fixture has a championship game; available:false when no postseason meeting.
- honesty: empty-input paths return available:false, never zeros.

**Frontend — extend `RivalriesPage.test.tsx`:** mock the bundle; assert each band renders,
gaps render the affordance (not 0), and the deep-links target the right routes.

**Gate:** backend pytest + ruff + mypy; frontend gen:api no-drift + typecheck + lint + Vitest;
update the `rivalries-chromium-linux.png` visual baseline (the page changes) in the VERIFY
session and run `npm run test:e2e` once.

---

## Done when

- `/rivalries` shows the matrix plus all five insight bands, each honest about gaps.
- Every superlative/streak/playoff/intensity row deep-links correctly (`/matchups/{id}` or
  `/rivalries/{a}/vs/{b}`); nemesis gaps show the affordance, never a zero.
- `closest_rivalry()` is no longer dead code (surfaced as the dead-even record).
- Full gate green; visual baseline regenerated; page clicked through.
- `PROGRESS.md` updated; work lands via a `feature/*` → `dev` PR with the trailer format.

---

## Open questions (resolve in BUILD if cheap, else ask)

- **Intensity weights/caps** — start at balance .30 / tightness .25 / recency .20 /
  volume .15 / stakes .10; `VOL_CAP=8`, `MARGIN_CAP=30`, recency half-life ~3 seasons.
  Tune once against the real DB so the ranking "feels right" to a league member.
- **Bracket coupling for finals labelling** — if joining `season_bracket` per season proves
  heavy, ship Playoff Rivalries on the `is_playoff` split alone and add the finals badge as a
  fast-follow rather than blocking the band.
