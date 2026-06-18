# P — Draft impact model (opportunity-cost-weighted steal/bust)

The deferred "Part C" follow-up to the draft genuine-zero work (dz-dashboard #85 /
danger-zone #52). Replaces the single points-over-expected `value` ranking of
steals/busts with a richer **composite "draft impact" score**, and extracts the
weighting shape (`base × cost × opportunity`) as a small reusable `analytics/`
primitive expected to recur elsewhere on the dashboard.

## Session model

Follows `PLAN → BUILD → VERIFY`.

- **PLAN: this document only.** No implementation in this thread.
- **BUILD:** the reusable weighting primitive, the draft composite scorer + roster-week
  helper, API schema fields + client regen, the DraftPage presentation, and scoped tests.
- **VERIFY:** full dashboard green gate, `gen:api` drift, frontend test, and a manual
  click-through of the 2015 draft page (Cruz vs Gordon ordering) on the real DB.

Read narrowly per the token budget: §7 of `04_ANALYTICS_MODEL.md`, the Draft rows of
`05_API_CONTRACT.md` / `07_PAGES_AND_VIEWS.md`, the draft lines of `08_TESTING_STRATEGY.md`,
and the existing `analytics/draft.py`. Do not open generated/lock files.

## Background — what already exists (build on, do not rebuild)

In `src/ff_dashboard/analytics/draft.py`:

- `VALUE_SLOT_WINDOW = 2`, `VALUE_DEFINITION`, `_expected_by_slot()`, `_value_history()`.
- `_with_values()` sets `value = season_points - expected` (the honest per-slot number).
- `_classify_pick_scoring()` already produces genuine `0.0` busts with
  `zero_reason="did_not_play_season"` for drafted-but-never-played skill players
  (Cruz 2015, Perriman 2015, Gordon 2016). These now flow into `value` as real busts.
- `_drafted_roster_slots() -> dict[int, set[str]]` returns the **set** of slots a drafted
  player occupied (used only to phrase the DNP note). Opportunity cost needs per-week
  **counts**, so add a sibling helper rather than changing this one.
- `BENCH_SLOTS` / `IR_SLOTS` are imported from `analytics/matchups.py`;
  `regular_season_weeks(session, season)` from `analytics/common.py` gives the denominator.
- `draft_value()` currently picks steals (top 3 `value>0`) / busts (bottom 3 `value<0`);
  `best_worst_picks()` is the all-time records book.

API: `api/schemas.py` `DraftPick` (overall, value, season_points, available, reason,
zero_reason, zero_detail), `DraftValue` (picks/steals/busts, definition, slot_window),
`DraftRecords`. Frontend: `web/src/features/draft/DraftPage.tsx`. Tests:
`tests/test_p8_draft_unit.py`, `web/src/features/draft/DraftPage.test.tsx`.

## The three factors (preserve the user's framing)

Steals/busts are **not** purely points over expected. The composite weighs:

1. **Base signal — points over/under expected.** Today's `value` (fantasy points). Sign:
   steal positive, bust negative. The base, **not** the sole signal.
2. **Draft cost.** An early-round bust is worse than a late-round bust; a late-round steal
   is better than an early-round steal. Monotonic in `overall`. Early picks spend more
   draft capital, so wasting them (bust) hurts more and beating them (steal) is expected;
   late picks cost little, so returning surplus is rarer/more impressive.
3. **Opportunity cost.** *How* the manager had to carry the player while waiting for a
   payoff. Carrying a non-producer on the **active bench** occupies a usable roster slot;
   stashing on **IR / reserve** does not. Canonical case: 2015 Victor Cruz = 11 weeks on
   the bench (an expensive bust); 2016 Josh Gordon = reserve/IR (cheaper to hold). Both are
   genuine-`0.0` busts after #85. **Opportunity cost amplifies busts only** — a steal
   produced, so carrying it was not wasteful (opportunity weight = 1 for steals).

## Composite formula (the editable proposal)

**Combination — multiplicative**, matching the user's stated shape `base × cost × opportunity`:

```
impact = value × cost_weight(overall, total_picks, is_steal) × opportunity_weight
```

- `value` carries the sign; both weights are ≥ 0, so the sign of `impact` equals the sign
  of `value` (steal = positive impact, bust = negative impact). A pick that exactly meets
  expectation (`value == 0`) has `impact == 0`.
- `impact` is in **weighted fantasy points** — still points-like and interpretable as a
  magnitude, just re-scaled by how the pick was spent and carried.
- **Recommended over a weighted sum of normalized components**: multiplication keeps the
  unit interpretable (a scaled point total), keeps the sign automatic, and matches the
  user's framing literally. A weighted sum would force an arbitrary normalization of points
  against unitless weights and lose the "amplify the honest number" intuition.

### `cost_weight` — directional capital curve

Let `r = (overall - 1) / (total_picks - 1) ∈ [0, 1]` (0 = first overall, 1 = last pick;
`total_picks` from `num_teams × rounds`, always derivable). Define one decreasing capital
curve and mirror it for steals:

```
capital(r)        = COST_FLOOR + (1 - COST_FLOOR) * (1 - r) ** COST_CURVE
cost_weight(bust) = capital(r)              # early bust (r→0) ≈ 1.0; late bust (r→1) → COST_FLOOR
cost_weight(steal)= capital(1 - r)          # mirror: late steal (r→1) ≈ 1.0; early steal → COST_FLOOR
```

So a late steal is weighted like an early bust — symmetric, one curve, two tunables.

### `opportunity_weight` — carry amplification (busts only)

From per-week roster slots that season, normalized by `regular_season_weeks`:

```
bench_frac = bench_weeks / reg_weeks      # weeks carried in an active bench slot
ir_frac    = ir_weeks    / reg_weeks      # weeks stashed in IR / reserve
opportunity_weight = 1 + OPP_BENCH_WEIGHT * bench_frac + OPP_IR_WEIGHT * ir_frac
```

Bounded in `[1, 1 + OPP_BENCH_WEIGHT + OPP_IR_WEIGHT]`. With `OPP_BENCH_WEIGHT > OPP_IR_WEIGHT`,
a full season on the bench amplifies a bust more than a full season on IR. For steals,
`opportunity_weight = 1.0` (no penalty). Weeks not rostered (player dropped) contribute
nothing — the opportunity cost ends at the drop.

### Proposed tunable weights — **editable; the user tunes these before BUILD**

Named, documented module constants (not opaque magic numbers; see
[[feedback-full-control-taxonomy]]). Echoed in the API payload so they are transparent.

| Constant | Meaning | Proposed | Sane range |
|----------|---------|---------:|-----------|
| `COST_FLOOR` | Capital still "spent" on the very last pick (so late picks aren't free) | `0.30` | 0.0 – 1.0 |
| `COST_CURVE` | Curvature of the capital decay (1 = linear, >1 = front-loaded) | `1.0` | 0.5 – 2.0 |
| `OPP_BENCH_WEIGHT` | Max bust amplification for a full season carried on the active bench | `1.0` | 0.0 – 2.0 |
| `OPP_IR_WEIGHT` | Max bust amplification for a full season stashed on IR / reserve | `0.25` | 0.0 – 1.0 |

**Worked check (the motivating case), equal base value & slot, 14-week season:**
- Cruz-like: 11 bench wks → `opp = 1 + 1.0·(11/14) = 1.79`.
- Gordon-like: full IR → `opp = 1 + 0.25·(14/14) = 1.25`.
- ⇒ Cruz's bust impact is ~1.43× more negative than Gordon's at the same `value` — the
  bench stash ranks as the more expensive bust, exactly the user's intuition.

## Missing-data fallback (honest degradation)

`team_rosters.roster_slot` history is 2010+ and sparse in early years.

- `cost_weight` is always computable (`overall` + `total_picks` always exist).
- When per-week bench/IR counts cannot be derived for a player-season,
  `opportunity_weight` **defaults to 1.0** — `impact` degrades honestly to
  `value × cost_weight`. **Never fabricate** opportunity cost and **never silently zero**
  `impact`. The pick is **not** marked unavailable for missing opportunity data; the base
  value is still honest.
- `impact` is non-null **iff** `value` is non-null. If `value` is null (a true gap or
  `insufficient_history`), `impact` is null too — no invented composite over a gap.
- An `opportunity_available: bool` flag in the component breakdown records whether roster
  weeks were found, so the UI can be honest about which factors fed the number.

## Reusable primitive — `analytics/weighting.py`

Keep the generic shape out of `draft.py`. Pure, no FastAPI, no DB.

```python
def weighted_impact(
    base: float,
    *,
    cost_weight: float = 1.0,
    opportunity_weight: float = 1.0,
) -> float:
    """A signed base metric scaled by a draft-cost weight and an opportunity factor.
    sign(result) == sign(base); identity weights return base unchanged."""
    return base * cost_weight * opportunity_weight


def positional_weight(
    position: int,
    span: int,
    *,
    floor: float = 0.0,
    curve: float = 1.0,
    invert: bool = False,
) -> float:
    """Monotonic weight in [floor, 1] over an ordered position 1..span.
    Decreasing by default (position 1 → 1.0, position span → floor);
    invert=True mirrors it (the steal curve)."""
```

`draft.py` computes its domain inputs (`cost_weight` via `positional_weight`,
`opportunity_weight` via the bench/IR fractions) and calls `weighted_impact`. The bench-vs-IR
opportunity factor stays in `draft.py` (domain-specific); the multiply and the monotonic
curve are the reusable parts.

## Helper / signature changes — `analytics/draft.py`

- Add module constants `COST_FLOOR`, `COST_CURVE`, `OPP_BENCH_WEIGHT`, `OPP_IR_WEIGHT`
  and an `IMPACT_DEFINITION` string (mirrors `VALUE_DEFINITION`, explains the composite).
- `_drafted_roster_weeks(session, season, player_ids) -> dict[int, dict[str, int]]` —
  sibling to `_drafted_roster_slots`. Per player, distinct-week counts:
  `{"bench": n, "ir": m, "weeks": total_distinct_weeks}` from `team_rosters`
  (`season_year`, `week`, `roster_slot`; week 0 excluded). Counts **distinct weeks** with a
  slot in `BENCH_SLOTS` / `IR_SLOTS` (roster rows are week-end snapshots —
  [[roster-snapshot-semantics]]).
- `_pick_impact(pick, *, reg_weeks, total_picks, roster_weeks) -> dict` — pure scorer:
  returns `impact` + an `impact_components` dict
  `{base_value, cost_weight, opportunity_weight, bench_weeks, ir_weeks, opportunity_available}`.
  Steal vs bust decided by `sign(value)`; opportunity applied only when `value < 0`.
- `_with_values()` (or a thin wrapper after it) layers `impact` / `impact_components` onto
  each scored pick using the helpers above.
- `draft_value()` — rank `steals` by **descending `impact`**, `busts` by **ascending
  `impact`**; keep `value` on every pick; add `impact_definition` + the echoed weights to
  the payload. `picks` still returns scored-first.
- `best_worst_picks()` (records book) — **decision below**.

## API schema changes — `api/schemas.py`

- `class ImpactComponents(BaseModel)`: `base_value: float`, `cost_weight: float`,
  `opportunity_weight: float`, `bench_weeks: int`, `ir_weeks: int`,
  `opportunity_available: bool`.
- `class ImpactWeights(BaseModel)`: `cost_floor`, `cost_curve`, `opp_bench_weight`,
  `opp_ir_weight` — the echoed tunables (transparency).
- `DraftPick`: add `impact: float | None = None` and
  `impact_components: ImpactComponents | None = None`.
- `DraftValue`: add `impact_definition: str` and `weights: ImpactWeights`.
- Run `npm run gen:api` + the drift check (`git diff --exit-code web/src/lib/api`).
  **Never hand-edit** the generated client.

## Frontend — `web/src/features/draft/DraftPage.tsx`

Presentation only; zero math.

- Steals/busts lists already arrive ranked by `impact` from the BFF — render in order.
- Make `impact` the headline number on each steal/bust line; keep `value`
  (points-over-expected) as a secondary, honest figure. A small tooltip / expandable shows
  `impact_components` (`cost ×`, `opportunity ×`, bench/IR weeks, `opportunity_available`).
- `BarCompare` (value-by-pick chart) plots `impact`; keep the per-slot `value` accessible.
- `PickCell` on the board keeps `season_points` + `value`; the genuine-0 `DnpMark` stays.
- New copy must explain the composite (surface `impact_definition`).

## Open decisions (resolved here; flagged for the user)

- **Combination:** multiplicative `base × cost × opportunity` (recommended) over a weighted
  sum — see formula rationale above.
- **Opportunity scope:** amplifies **busts only**; steals get `opportunity_weight = 1.0`.
- **Records book (`best_worst_picks`, `/v1/records/draft`):** **keep ranking on raw
  `value`** (recommended). Rationale: the all-time records book needs cross-season
  comparability, and opportunity data is sparse/absent pre-2010 — ranking ever-records by a
  factor only half the seasons can carry would be dishonest. The per-season draft page is
  where `impact` belongs. (Still attach `impact`/`impact_components` to those picks for
  display, just don't sort by it.) *User may override to rank records by impact.*
- **`value` retained:** the composite is **additive**; the honest per-slot `value` field
  stays on every pick and visible in the UI.

## Test list

**Primitive — `tests/test_weighting_unit.py` (pure):**
- `weighted_impact`: identity weights return `base`; multiplies all three; preserves sign;
  `base == 0 → 0`.
- `positional_weight`: position 1 → 1.0, position `span` → `floor`; monotonic decreasing;
  `invert=True` mirrors; `curve` exponent changes shape but keeps endpoints; `span == 1`
  edge case.

**Draft scorer — extend `tests/test_p8_draft_unit.py` (pure, no DB where possible):**
- Opportunity ordering: same base `value` + same slot, **bench-carry bust** is more
  negative than **IR-carry bust** is more negative than **dropped/never-rostered bust**.
- Draft cost: same `value`, **early bust** more negative than **late bust**; **late steal**
  larger positive than **early steal**.
- Steals get **no** opportunity penalty (`opportunity_weight == 1.0`) even with bench weeks.
- Missing roster data → `opportunity_available == False`, `opportunity_weight == 1.0`,
  `impact == value × cost_weight` (honest degrade), `impact` not null.
- `impact` is null **iff** `value` is null (gap / `insufficient_history`).
- The motivating case: a Cruz-like bench bust outranks a Gordon-like IR bust at equal
  `value` & slot.

**Integration over the fixture (`tests/test_p8_draft_unit.py`):**
- `draft_value()` sorts `steals` by descending and `busts` by ascending `impact`;
  every scored pick carries `impact_components`; `impact_definition` + `weights` present.
- Fixture coverage: reuse / extend the genuine-0 fixture so a bench-carried zero and an
  IR-carried zero exist to order. (The fixture has no 2015 draft; add minimal rows per the
  #85 fixture additions.)

**Contract / frontend:**
- `npm run gen:api` drift check clean after the schema change.
- `DraftPage.test.tsx`: renders `impact` headline + `value` secondary; shows the components
  tooltip; respects BFF ordering; a crafted-props case where a bench bust precedes an IR
  bust.

## Done when (this PLAN session)

- This document is committed on `feature/draft-impact-model` with: the chosen multiplicative
  formula, the four named tunable weights as an editable proposal table, the
  helper/endpoint/schema signatures, the missing-data fallback rule, the reusable-primitive
  location + signature, and the test list. **Then stop for the user to tune the weights and
  approve** before a BUILD session.

## Done when (the eventual BUILD/VERIFY, for reference)

- `analytics/weighting.py` primitive exists, pure and unit-tested.
- `draft.py` composite ranks steals/busts by `impact`; `value` retained; opportunity
  degrades honestly when roster data is missing; genuine-0 classification from #85 still
  works (Cruz/Gordon are the fixtures).
- Schema fields land; `gen:api` drift clean; DraftPage renders the composite + components.
- Full green gate (backend pytest + ruff + mypy; frontend gen:api drift + typecheck + lint +
  test); forbidden-import/write check clean for `src/ff_dashboard`; manual click-through of
  the 2015 draft page on the real DB confirms Cruz ranks as a worse bust than Gordon.

## Out of scope / follow-ups

- Reusing `weighting.py` on other pages (the shape is expected to recur) — separate slices.
- Any change to the genuine-0 classifier itself (shipped in #85).
- Records-book re-ranking by impact (left on `value` by decision above unless the user
  overrides).
