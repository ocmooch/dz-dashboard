# fix-P1 — Analytics correctness, scoping & enrichment

PLAN doc for fix-pass **P1** of the 2026-06 review program
(`docs/plans/REVIEW_FIXES_ROADMAP.md`). Authoritative scope lives in the review doc
(`docs/reviews/2026-06-in-browser-review.md` § "P1 — Analytics correctness, scoping &
enrichment" + findings F-32, F-22, F-31, F-10, F-12, F-23, F-17, F-13). This expands it into
files / signatures / known-answer tests. **BUILD against this; don't re-explore.**

> **Layer:** P1 is **backend-only** (analytics + API schema + tests + `gen:api` drift). The
> frontend that renders these new fields is **P5/P6** — see "Frontend tail" per finding. The P1
> gate is backend pytest+ruff+mypy **and** `gen:api` drift clean; no vitest / click-through.

## Done when (sharpened from the review doc)

- A per-season **season-schedule model** exists, config-driven, seeded with known values, with
  switch-years left as user-supplied config (`TODO(input: season-length switch year)`); every
  analytics consumer of week structure reads it (no new hardcoded 14/17).
- **Team/score/season records** (`highest_team_score`, `lowest_team_score`, `biggest_blowout`,
  `narrowest_win`, `highest_scoring_matchup`, `best/worst_season_points_for`) are computed over
  **all seasons with team totals (2010–2025)**; only player-dependent records (`best_player_week`)
  stay scoped to the scored era (2016–2025). A test proves a pre-2016 game/season **can** take a
  record.
- **Season totals** count **fantasy weeks only** (≤ the season's championship week from the model);
  NFL post-season weeks beyond the fantasy schedule are excluded.
- **Owner season table** carries a derived per-season **`result`** (champion / runner-up / 3rd /
  Nth) on every completed row (incl. 2010–2015), and a data-derived **`made_playoffs`** (no longer
  always `null`).
- **Head-to-head** gains `closest_meeting{…,matchup_id}` and `cumulative_margin_for_a`; the
  existing `most_lopsided_meeting`/`highest_scoring_meeting` carry `matchup_id` (already present).
- **Week matchups** gain `is_close` + `is_blowout` (backend thresholds, documented constants) and
  per-side **`entering_record`** {wins, losses, ties}.
- Backend `pytest + ruff + mypy` green; `npm run gen:api` drift clean (schemas regenerated).

## Build order (data/foundation → consumers)

1. **Season-schedule model** (F-32) — everything else reads it.
2. **Records era split** (F-22) — `team_record_window` vs `scored_window`.
3. **Season-totals week cap** (F-31) — dashboard-owned aggregation using the model.
4. **Owner season result** (F-10).
5. **Head-to-head enrichment** (F-12 / F-23).
6. **Week-matchups flags + entering record** (F-13 / F-17).

---

## 1. Season-schedule model (F-32) — the foundation

**New file** `src/ff_dashboard/analytics/season_schedule.py`.

```python
@dataclass(frozen=True)
class SeasonSchedule:
    season_year: int
    regular_weeks: int             # regular season = weeks 1..regular_weeks
    playoff_weeks: tuple[int, ...] # the fantasy-playoff week numbers
    championship_week: int         # the final/title week (== last fantasy week)
    is_estimated: bool             # True when from DB/default, not a confirmed config entry

def season_schedule(session: Session, season: Season) -> SeasonSchedule: ...
def fantasy_week_range(s: SeasonSchedule) -> range:        # range(1, championship_week + 1)
def phase_of_week(s: SeasonSchedule, week: int) -> str:    # "regular"|"playoff"|"championship"|"out_of_season"
```

**Config + seeded default (switch-years TBD):**

```python
_MODERN = dict(regular_weeks=14, playoffs=(15, 16, 17), championship=17)
# Confirmed historical overrides keyed by season_year. EMPTY until the user supplies the
# 1-13 -> 1-14 switch season; then enumerate pre-switch seasons as
# regular_weeks=13, playoffs=(14,15,16), championship=16.
_CONFIRMED: dict[int, dict] = {}  # TODO(input: season-length switch year) — roadmap input #1
```

Resolution order in `season_schedule()`:
1. `_CONFIRMED[year]` if present → `is_estimated=False`.
2. else fall back to the DB column via existing `common.regular_season_weeks(session, season)`
   for `regular_weeks`, and `_MODERN` for playoff/championship shape → `is_estimated=True`.

**Seeded default = no behaviour change yet.** With `_CONFIRMED` empty, every season resolves to
its current DB-derived `regular_weeks` + modern playoff shape, so standings/records/power outputs
are unchanged. The deliverable is the *model + phase helper + routing consumers through it*, ready
for the switch-year. (F-32's `regular_season_weeks:14` for 2010 stays as-is, gated to the input.)

**Known-answer tests** (`tests/dashboard/test_season_schedule.py`):
- `phase_of_week`: modern season → wk 1 & 14 = "regular", wk 15/16 = "playoff", wk 17 =
  "championship", wk 18 = "out_of_season".
- `fantasy_week_range(modern)` == `range(1, 18)`.
- `is_estimated` True for a season with no `_CONFIRMED` entry; flips False + uses 13/16 shape when a
  fixture-only `_CONFIRMED` entry is injected (proves the switch-year path works before the real
  value lands).
- Gap case: a season whose DB `regular_season_weeks` is NULL falls back to max-played-week (via
  `common.regular_season_weeks`) without raising.

---

## 2. Records era split (F-22)

**Touch** `src/ff_dashboard/analytics/records.py:records_book` (and helper).

Today `records_book` filters **all** matchups to `scored_season_ids`. Split the windows:

```python
def scored_window(session) -> set[int]:        # season_ids where year in seasons_scored()  (2016–2025)
def team_record_window(session) -> set[int]:   # season_ids with team totals: any Matchup.team_score not NULL (2010–2025)
```

- Compute `highest_team_score`, `lowest_team_score`, `biggest_blowout`, `narrowest_win`,
  `highest_scoring_matchup` over `team_record_window` (query matchups across **all** those
  seasons, not `scored_season_ids`).
- Keep `best_player_week` on `scored_window` (it joins `PlayerStatsScored`, inherently scored-era).
- `best/worst_season_points_for`: already full-history (uses `_standings_index`, which spans every
  season) — **add a test to lock it**, no code change expected.
- Keep the informational `scored_era` list in the payload (it documents the player-record window).
  Consider adding `team_record_era` (sorted years with team totals) for honesty — **optional**,
  only if it doesn't churn the contract beyond the planned additions.

**Known-answer tests** (extend `tests/dashboard/test_records.py`): seed the fixture so a **pre-2016**
team game holds `highest_team_score` (or `biggest_blowout`) and assert the record's
`season_year < 2016`; assert `best_player_week.season_year >= 2016` still. Verify on the real DB
during VERIFY whether any pre-2016 game/season actually takes a record (note the answer in PROGRESS).

---

## 3. Season-totals week cap (F-31)

**New file** `src/ff_dashboard/analytics/stats.py` — own the aggregation in analytics (math belongs
here; today the route imports the Phase-1 `ff_pipeline...queries.season_totals`, which sums **all**
weeks with no cap → NFL post-season inflation).

```python
def season_totals(session: Session, season: Season, *, position: str | None = None) -> list[dict]:
    # Sum PlayerStatsScored.total_points per player WHERE week <= schedule.championship_week,
    # using season_schedule(session, season). Same output shape as today's SeasonTotals rows
    # (player_id, name_full, position, nfl_team, total_points, weeks_played).
```

**Route change** `api/routes/players.py`: import the new analytics `season_totals` instead of the
Phase-1 query; pass the resolved `Season`. **Response shape unchanged** → no `gen:api` drift for
this endpoint (values change only).

> Cross-repo note: the Phase-1 `queries.season_totals` is left untouched (sibling repo, read-only
> boundary). We do **not** modify it; we own a week-capped aggregation dashboard-side. Logged in the
> roadmap considerations.

**Known-answer tests** (`tests/dashboard/test_stats.py`): fixture with a player who has points in a
fantasy week (≤ championship) **and** a beyond-championship week; assert the beyond-championship
points are excluded and `weeks_played` counts only fantasy weeks. Gap case: an unscored (pre-2016)
season returns `[]` (no `player_stats_scored`), not a zero-filled row.

---

## 4. Owner season result (F-10)

**Touch** `src/ff_dashboard/analytics/owners.py:owner_seasons`.

`made_playoffs` is `null` for every row (DB column unpopulated) while `final_rank`/`is_champion` are
present. Derive both in analytics:

- **`result`** (string, available whenever `final_rank` present — all completed seasons incl.
  2010–2015): `is_champion` → `"Champion"`; `final_rank == 2` → `"Runner-up"`; `== 3` →
  `"3rd place"`; else `f"{final_rank}th"`. `None` when `final_rank` absent (in-progress) → gap, not 0.
- **`made_playoffs`** (bool | None): derive from data — a team made the playoffs iff it has ≥1
  `Matchup` row with `is_playoff == True` that season. `None` only when the season has no playoff
  matchups recorded at all (don't fabricate False).
  - **Caveat to resolve in BUILD:** if the fixture/real DB flags **consolation/toilet-bowl** games
    as `is_playoff=True`, this over-counts. BUILD must check the fixture; if consolation games are
    flagged, gate on a `playoff_teams` count added to the schedule model (`final_rank <=
    playoff_teams`) instead. Default to the `is_playoff`-presence derivation and lock it with a test.

**Known-answer tests** (extend `tests/dashboard/test_owners.py`): a champion season → `result ==
"Champion"`, `made_playoffs True`; a known non-playoff finisher → `made_playoffs False`; a
pre-2016 completed season → `result` populated (not None). Gap case: in-progress / rank-less season
→ `result None`, no zero.

**Frontend tail (P5, not P1):** F-10 also wants the manager season table to *render* the result —
that's `web/src/features/managers/` and lives in P5. P1 only supplies the field.

---

## 5. Head-to-head enrichment (F-12 + F-23)

**Touch** `src/ff_dashboard/analytics/head_to_head.py:pairwise_record`. The `agg["meetings"]` list
already carries each meeting's `low_score/high_score/low_margin/season_year/week/matchup_id`, and
`a_margin_total` is already computed — both additions are cheap:

- **`cumulative_margin_for_a`** (float): `round(a_margin_total, 2)` — the signed total +/- across
  all meetings (distinct from the existing per-game `avg_margin_for_a`).
- **`closest_meeting`** (object, mirror of `most_lopsided_meeting` but **min** |margin|):
  `min(agg["meetings"], key=lambda mt: abs(mt["low_margin"]))` → `{season_year, week, matchup_id,
  margin_for_a}` (sign-oriented to A like the lopsided one). Deep-linkable.

Surfaced via `GET /v1/owners/{a}/head-to-head/{b}` (schema `HeadToHead` in `api/schemas.py`).

**Schema (gen:api drift):** add `cumulative_margin_for_a: float` and `closest_meeting: <same shape
as MostLopsidedMeeting>` to the head-to-head response schema. Run `gen:api` + drift check.

**Known-answer tests** (extend `tests/dashboard/test_head_to_head.py`): fixture pair with ≥3
meetings of known margins → assert `cumulative_margin_for_a` == signed sum, `closest_meeting.matchup_id`
== the smallest-|margin| game, sign-oriented to A. Symmetry: B-vs-A `cumulative_margin_for_a` ==
−(A-vs-B). Gap case: `available:false` pair (no meetings) omits the new fields gracefully.

**Frontend tail (P5):** surfacing `most_lopsided`/`highest_scoring`/`closest` with deep-links in the
manager-profile rivalry snapshot and the pairwise rivalry page is **P5** (F-12/F-23 frontend). P1
provides the data + links.

---

## 6. Week-matchups flags + entering record (F-13 + F-17)

**Touch** `src/ff_dashboard/analytics/matchups.py:week_matchups` (+ `team_ref`).

**Close/blowout flags (F-13)** — move the threshold backend (frontend currently hardcodes
`margin >= 40` in `MatchupsPage.tsx:58`, violating "no metric math in web"). Documented constants:

```python
CLOSE_MARGIN = 5.0       # decided/tied game within 5 pts
BLOWOUT_MARGIN = 40.0    # mirrors the current frontend threshold
```

Per game card: `is_close = margin is not None and margin <= CLOSE_MARGIN`;
`is_blowout = margin is not None and margin >= BLOWOUT_MARGIN`. (Both False when scores absent.)

**Entering record (F-17)** — per side, the team's regular-season W-L-T from weeks **before** this
week, that season. Add to `team_ref`: `entering_record: {wins, losses, ties}` (computed from prior
`Matchup` rows for that `team_id` in the season, weeks `< week`, regular season only via the
schedule model's `regular_weeks`). Compute once per request (one query for the season's matchups,
fold per team up to `week-1`) — don't N+1.

**Schema (gen:api drift):** add `is_close: bool`, `is_blowout: bool` to the week-matchups game card
schema; add `entering_record: {wins:int, losses:int, ties:int}` to the team-ref schema in
`api/schemas.py`. Run `gen:api` + drift check.

**Known-answer tests** (extend `tests/dashboard/test_matchups.py`): a 3-pt game → `is_close True,
is_blowout False`; a 45-pt game → `is_blowout True, is_close False`; a wk-3 matchup where a team is
2-0 entering → `entering_record == {wins:2, losses:0, ties:0}`; wk-1 → all zeros. Gap case: a game
with `None` scores → both flags False, entering record still computed from prior decided games.

**Frontend tail (P5):** consuming `is_blowout`/`is_close` (replacing the hardcoded `>=40`) and
coloring margins is F-13/F-14 in **P5**. P1 supplies the flags.

---

## Files at a glance

| Action | Path |
|--------|------|
| **create** | `src/ff_dashboard/analytics/season_schedule.py` |
| **create** | `src/ff_dashboard/analytics/stats.py` (season-totals, week-capped) |
| edit | `src/ff_dashboard/analytics/records.py` (era split) |
| edit | `src/ff_dashboard/analytics/owners.py` (`owner_seasons` result/made_playoffs) |
| edit | `src/ff_dashboard/analytics/head_to_head.py` (`pairwise_record` enrichment) |
| edit | `src/ff_dashboard/analytics/matchups.py` (`week_matchups` flags + entering record) |
| edit | `src/ff_dashboard/api/schemas.py` (head-to-head, week-matchups, owner-season fields) |
| edit | `src/ff_dashboard/api/routes/players.py` (season-totals → analytics import) |
| edit | `src/ff_dashboard/api/routes/*` as needed for the new fields |
| **create** | `tests/dashboard/test_season_schedule.py`, `tests/dashboard/test_stats.py` |
| edit | `tests/dashboard/test_records.py`, `test_owners.py`, `test_head_to_head.py`, `test_matchups.py` |
| regen | `web/src/lib/api/` via `npm run gen:api` (drift check; never hand-edit) |

## Docs to update on BUILD/VERIFY

- `docs/04_ANALYTICS_MODEL.md`: §5 records (era split), §4 head-to-head (closest/cumulative), §3
  matchups (close/blowout, entering record), §6 owners (season result); a short note on the new
  season-schedule model.
- `docs/05_API_CONTRACT.md`: head-to-head excerpt (+2 fields), week-matchups card (+flags +entering
  record), owner-seasons row (+result).
- `PROGRESS.md` + roadmap row P1 (◐ on BUILD, ☑ on merge); mark F-32/F-22/F-31/F-10/F-12/F-23/F-17/F-13
  with the resolving PR.

## Open inputs / TODOs

- `TODO(input: season-length switch year)` — roadmap input #1 (1-13 → 1-14). Until supplied, the
  model is config-driven with the modern default; standings `regular_season_weeks` for early
  seasons stays as the DB value. When supplied: fill `_CONFIRMED`, re-run the gate, verify standings
  for the affected seasons.
- BUILD must resolve the `made_playoffs` consolation-bracket caveat against the fixture (§4).
