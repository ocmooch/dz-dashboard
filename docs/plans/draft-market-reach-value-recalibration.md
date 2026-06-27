# P — Draft Market axis: reach/value recalibration

Recalibrate the **reach / value** label on the draft **Market** lens so it reads the way an
informed drafter actually judges a pick. The axis itself (where this league drafted a player vs
the consensus ADP) is unchanged and correct; what's wrong is the **threshold** that turns the
`adp_delta` into a label.

This is a PLAN doc only — no implementation in this thread. Single-repo (dz-dashboard); the math
lives in `analytics/adp.py`. The companion upstream data-coverage gap is recorded in
`docs/ACTIVE_WORK.md` §2 ("ADP source coverage — FFC 2025") and is **not** a prerequisite: the
model must degrade gracefully when a season's ADP is thin.

## The problem

`market_axis()` (`analytics/adp.py`) compares a pick's `overall` to a single blended ADP point
estimate with a **flat ±1.0-slot dead-band** (`ON_MARKET_BAND`). Anything more than one slot
earlier than the point ADP is labelled `reach`. That over-fires badly at the top of the draft,
where the elite tier is interchangeable and ordering is preference:

- **2025, Bijan Robinson** — blended ADP ≈ **4.1** (MFL 4.64, range 1–11; Sleeper 3.3; **no FFC**
  — see the coverage gap below). Taken **1st overall** → `delta = 1 − 4.1 = −3.1` → past the
  ±1 band → **"Reach by 3.1."** But MFL's own data shows he went as early as pick 1 in real
  drafts; 1.01 is not a reach. The flat band can't tell "preference noise at the top" from a
  genuine early grab.

An owner doesn't read ADP as a point with a 1-slot tolerance. Being 3 picks "off" in Round 1 is
precise disagreement; being 3 picks off in Round 13 is rounding error. The tolerance must **grow
with draft depth**, and the very top deserves extra grace because it's preference-driven.

## Decision (locked with the owner)

Replace the flat band with a **depth-scaled on-market cushion**:

```
cushion(adp) = max(CUSHION_FLOOR, CUSHION_SLOPE * sqrt(adp))      # in pick slots
delta        = overall - adp                                       # unchanged; + = value, - = reach
label        = value     if delta >  cushion
               reach     if delta < -cushion
               on_market otherwise
```

with **`CUSHION_FLOOR = 4.0`** and **`CUSHION_SLOPE = 2.5`**.

- **`sqrt(adp)` slope** — tolerance starts small at the top and widens fast, then flattens,
  mirroring how draft certainty decays. This *is* the early/middle/late weighting; it falls out
  of the curve, so no separate per-round rules.
- **`max(4, …)` floor** — protects the consensus elite, where 1.01 vs 1.05 is pure preference.
  The floor only bites below ≈ADP 2.6 (where `2.5·√adp` < 4); the entire mid-and-late curve is
  untouched.

Worked cushions and the owner's three gut-checks:

| ADP | cushion (± picks) | check |
|-----|-------------------|-------|
| 1 (consensus #1) | 4.0 (floored) | taken at pick 5 → on-market (was pick 3.5); reflects preference |
| 4.1 (Bijan) | 5.06 | taken 1st (Δ −3.1) → **on_market** ✓; falls to 11 (Δ +6.9) → **value** ✓ |
| 12 (end Rd 1) | 8.66 | — |
| 36 (Rd 3) | 15.0 | — |
| 100 (Rd 9) | 25.0 | DST whose ADP is Rd 11 taken Rd 5 (Δ ≈ −75) → big reach; Rd 9 (Δ ≈ −30) → small reach ✓ |
| 150 (Rd 13) | 30.6 | — |

The floor and slope are **two independent knobs**, each documented and echoed in the payload
(same transparency pattern as `ADP_SOURCE_WEIGHTS` and the impact weights). If a consensus #1
should tolerate a pick-6 grab, raise the floor to 5; past ~5 it starts eroding the
falls-to-Round-2 value signal, so stop there.

### Magnitude display — unchanged unit, finer grain

`adp_delta` stays the **raw `overall − adp` in picks** (today's unit, finest grain). The
**label** keys off the cushion; the **number** always tells the literal truth. So a pick can
read "Value by 7" and be `value`, while a deep flier also "Value by 7" sits inside its wider
cushion → `on_market`. Label and number stay independent. The UI keeps showing picks (not
rounds): finer-grained and more accurate, if less colloquial.

### Why not the alternatives

- **A — observed-range band** (on-market if `overall ∈ [adp_high, adp_low]`): rejected. Bijan's
  real range was 1–11, so it would call a pick-11 grab "on market" — but an RB1 falling to 11 is
  a *value*. The range treats its whole span as equally acceptable; it can't distinguish the
  edges from the center.
- **C — widen the flat band to ~6**: rejected. Arbitrary and flat; treats pick 1 and pick 150
  identically. Often "correct" by accident, never principled.

## Files to touch

- **`src/ff_dashboard/analytics/adp.py`** — the core change.
  - Remove `ON_MARKET_BAND`; add `CUSHION_FLOOR = 4.0`, `CUSHION_SLOPE = 2.5`, and a pure
    `on_market_cushion(adp) -> float` helper.
  - Rewrite `market_axis()` internals to use `on_market_cushion(adp)` (signature unchanged:
    `market_axis(adp, overall)`).
  - Update `ADP_DEFINITION` to describe the depth-scaled cushion in plain terms (replaces the
    "drafted earlier than ADP is a reach, later is a value" sentence, which implies a hard line).
  - Add a season-level coverage helper (see below).
- **`src/ff_dashboard/analytics/draft.py`** —
  - The per-pick wiring (`market_axis(blend["adp"], p["overall"])`) is unchanged.
  - **Leaderboards** (`draft_value` reaches/values, ~L911–917): today they filter on
    `adp_delta < 0` / `> 0`. Switch to filtering on **`market_label == "reach"` / `"value"`** so
    a pick inside its cushion (`on_market`) never appears as a small "reach/value." Ordering by
    `adp_delta` magnitude stays.
  - **Tendencies** (`draft_tendencies`, ~L1033): already keys off `market_label`, so the
    recalibration flows through automatically — `reach_rate` / `value_rate` will drop to
    sensible levels. Add a regression assertion, don't rewire.
  - Add the season-level `adp_coverage` block (below) to the `draft_board` / `draft_value`
    payloads.
- **`src/ff_dashboard/api/schemas.py`** — add the season-level `adp_coverage` object to the draft
  board/value schemas (`limited: bool`, `sources: list[str]`, `note: str | None`). Per-pick
  fields unchanged. Run `npm run gen:api`; commit the regen.
- **`web/src/features/draft/DraftPage.tsx`** — the Market lens reads the new `adp_coverage`; when
  `limited`, show one quiet, non-alarming line (see below). Per-pick chips already read
  `market_label` / `adp_delta` and need no change.
- **Tests** — `tests/test_adp_market_axis.py` (recalibrate the fixture expectations — see Test
  list); `tests/test_p8_draft_unit.py` if it asserts specific reach/value labels.

## 2025 honesty affordance — limited ADP coverage

Some seasons lack the draft-week FFC snapshot (the only source carrying the full high/low/stdev
spread, aggregated over late August). **2025** is the live case: FFC has no 2025 data at source,
so the blend is MFL (whole-offseason aggregate) + Sleeper only — wider-window and softer. The
reach/value reads for such seasons are genuinely less precise, and we say so without overstating.

- Season is **limited** when its blended sources for the season do **not** include `ffc`. Derive
  it from the already-built `season_adp_map` (union of `adp_sources` across players) — no new
  query.
- Payload: `adp_coverage = {"limited": true, "sources": ["mfl", "sleeper"], "note": "ADP coverage
  is limited this season — based on wider-window sources (no draft-week snapshot), so reach/value
  reads are less precise."}`. `limited: false` (note `null`) otherwise.
- UI: render the `note` once on the Market lens (a muted caption, not a warning banner). Recorded
  for honesty; not editorialized.

This is intentionally **data-driven**, never a hardcoded year — if FFC restores 2025 (or any
season loses FFC), the flag follows the data. Consistent with the repo's no-hardcoded-year rule.

## Test list

`tests/test_adp_market_axis.py` (pure-math, no DB — the cheap canaries):

- `on_market_cushion`: `adp 1 → 4.0` (floored), `adp 2 → 4.0` (floored), `adp 4 → 5.0`,
  `adp 100 → 25.0` (slope), monotonic non-decreasing.
- `market_axis` cushion behavior:
  - Bijan: `market_axis(4.1, 1)["market_label"] == "on_market"`;
    `market_axis(4.1, 11)["market_label"] == "value"`.
  - Consensus #1: `market_axis(1.0, 5)` → `on_market`; `market_axis(1.0, 6)` → `value`.
  - Deep reach: `market_axis(130, 55)` → `reach` (Δ −75 past cushion ≈ 28.5).
  - On the nose: `market_axis(2.0, 2)` → `on_market`.
  - **Recalibrate existing fixtures** that assumed the old ±1 band — e.g.
    `market_axis(1.0, 4)` is now `on_market` (Δ 3 < cushion 4), not `value`; the fixture-DB
    McCaffrey-@4-ADP-1.0 case in `test_board_picks_carry_market_axis` /
    `test_value_reaches_and_values_leaderboards` must be re-pointed to a pick whose delta clears
    its cushion (or the fixture ADP/overall adjusted) so a real reach/value still asserts.
- `market_axis(8.4, 1)` stays `reach` (Δ −7.4 > cushion 7.25) — confirms the change doesn't
  silence genuine top-of-draft reaches.

DB-backed:

- `draft_value` leaderboards: every entry has `market_label in {"reach","value"}` (no
  `on_market` leakage); reaches negative-delta, values positive-delta, never crossed.
- `draft_tendencies`: `reach_rate` / `value_rate` recompute against the new labels (assert a
  manager who only truly reached still reads high; the rates are lower than under ±1).
- `adp_coverage`: a season with FFC present → `limited: false`; a season blended without FFC →
  `limited: true` with the note string and the source list.
- `gen:api` drift clean after the schema add.

## Done when

- `analytics/adp.py` uses `cushion(adp) = max(4, 2.5·√adp)`; `ON_MARKET_BAND` is gone;
  `ADP_DEFINITION` describes the depth-scaled cushion; both knobs are module constants.
- `adp_delta` magnitude unchanged (raw picks); only labels move.
- Draft leaderboards filter by `market_label`; tendencies recompute through it.
- Limited-coverage `adp_coverage` block is data-driven (FFC-absence), surfaced as one quiet line
  on the Market lens; no hardcoded year.
- Full gate green (backend pytest + ruff + mypy; FE `gen:api` drift + typecheck + lint + test);
  manual click-through of the 2025 draft Market lens — Bijan reads `on_market`, the limited-data
  note shows — and a season **with** FFC (e.g. 2024) where the note is absent.

## Upstream dependency (recorded, not blocking)

The model is built to **degrade**, not wait. The data-side improvement — restoring FFC for 2025
so the season gets a real draft-week spread — is an **upstream (danger-zone)** item recorded in
`docs/ACTIVE_WORK.md` §2. It depends on **FFC republishing 2025 ADP**, which may happen
eventually or never; it is *not* something we can force with immediate effort. When/if it lands,
re-ingest backfills the season, the `adp_coverage` flag clears itself, and the reach/value reads
sharpen — with **no dashboard code change** (read-only seam). This recalibration ships regardless.
