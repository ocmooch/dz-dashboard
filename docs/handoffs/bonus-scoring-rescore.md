# Handoff — danger-zone: seed per-season bonus rules + re-score (F-27 validation half)

**Audience:** ff-pipeline (`../danger-zone`) work. **Authored from:** dz-dashboard investigation
2026-06-22. **Companion:** `dz-dashboard/docs/plans/bonus-scoring-fidelity.md` (the dashboard half +
shared diagnosis). **Tracks:** F-27 (reconstructed-scoring trust check) + the per-season config ledger.

---

## Problem

`player_stats_scored.total_points` (the scoring reconstruction) carries **no NFL.com scoring bonuses** —
verified: **0 of ~390k** rows have a `bonus` component in `points_breakdown`; only base categories
`passing/rushing/receiving/kicking/misc`. The authoritative bonus-inclusive league score is
`team_rosters.extra_data.nfl_com_points`, present **only on rostered player-weeks** (46,521 rows). The
two diverge league-wide, every season 2010–2024 (~140–220 rostered rows/season, ~390–680 pts/season).

Canary: Mike Vick `player_id=23907`, 2010 wk10 → `total_points=58.32` vs `nfl_com_points=63.32`.

The engine **already supports** this: `scoring/engine.py` handles flat threshold bonuses (`flat_points`,
`threshold_min/max`); `scoring/rules.py` defines the rule shape; `crawlers/nflverse/long_td_bonus.py`
exists; engine comment notes nflverse long-TD bonuses were **"deferred to M7."** So the gap is **the
per-season bonus rules were never fully seeded / the long-TD path never wired**, not a missing feature.

## Goal

Make `total_points` authoritative league-wide by adding the league's per-season bonus rules as a
**separate, year-matched settings layer** on top of **unadulterated** raw stats, then re-scoring
2010–2025. Validate against `nfl_com_points` (ground truth) on rostered weeks.

## Constraints (owner decisions — do not deviate)

- **Raw stats stay unadulterated.** Bonuses live in the scoring/settings layer, never written back onto
  ingested raw rows.
- **Per-season, year-matched.** League scoring settings changed over history — see
  `dz-dashboard/docs/archive/seasons-league-changes-inventory.md` and the config-ledger work. Do not
  apply one flat ruleset across all seasons.
- **Apply bonuses uniformly to all players** (roster-agnostic pure function), **not** conditional on
  roster membership — so a player later joining a roster needs **no** re-score. Never-rostered players
  stay in the DB; the dashboard hides them at the view layer.
- **No contract/shape change** to `player_stats_scored` (values change, columns don't). Bonuses should
  appear as a `bonus` component in `points_breakdown` for transparency.

## What the bonus structure looks like (reverse-engineering aid)

Distribution of `nfl_com_points − total_points` over the 39,512 rostered rows that have both
(2,635 carry a delta):

| delta | rows | likely source |
|---|---|---|
| **+4.00** | 1233 | dominant bonus (spans QB/WR/RB/DEF) — yardage milestone and/or long-TD |
| **+1.00** | 741 | smaller milestone |
| +6 / +5 / +8 / +7 | 154 / 81 / 70 / 20 | combinations (multiple bonuses one week) |
| +2 / +3 | 46 / 14 | |
| **−1 / −2 / −3 / −4** | 53 / 95 / 44 / 8 | ⚠️ reconstruction **over**-counts here — a *separate* fidelity bug (not a bonus); see below |

Positive-delta rows by position: **QB 821, WR 773, DEF 392, RB 347, TE 74** → passing, receiving,
rushing **and DST** bonuses are all in play. `nfl_com_points` is the ground truth to fit the exact
thresholds/values against; cross-check with the league's NFL.com scoring-settings history per season.

## ⚠️ Secondary finding — the negative-delta class (~200 rows)

~200 rostered rows have `total_points > nfl_com_points` (reconstruction over-counts vs NFL.com). Bonuses
can't explain these — they're a distinct accuracy bug (stat-source discrepancy, an unmodeled NFL.com
penalty, or DST scoring differences — note the existing `dst-yards-sacks-pipeline-gap`). The 0.1
validation gate below will flag them; they need a root-cause pass, not just bonus addition.

## Steps

1. **Inventory** the league's bonus rules per season (NFL.com settings history) and reverse-engineer
   exact thresholds/values from the delta data above; seed them into the per-season scoring rule config.
2. **Wire** the M7-deferred nflverse long-TD bonus (`crawlers/nflverse/long_td_bonus.py`) into scoring.
3. **Re-score** 2010–2025 (`scoring/rescore.py`); record bonuses as a `bonus` key in `points_breakdown`.
4. **Validation gate:** for every rostered week, `|total_points − nfl_com_points| ≤ 0.1` across all
   46,521 rows. Add the canary (Vick 2010 wk10 = 63.32) and a representative set to the scoring test
   suite. Triage the negative-delta class separately.
5. **Reload** `data/fantasy.db` (dashboard `AnalyticsCache` auto-invalidates on the new `pipeline_run_id`).

## Acceptance

- Rostered `total_points` matches `nfl_com_points` within 0.1 across all seasons; `points_breakdown`
  carries a `bonus` component where applicable.
- Never-rostered players re-scored with the same uniform rules (no ground truth to check, correct by
  construction).
- Once shipped, the dashboard BFF `coalesce(nfl_com_points, total_points)` interim can be retired
  (the displayed numbers come from one authoritative source again).

## Cross-refs

`dz-dashboard/docs/plans/bonus-scoring-fidelity.md` · F-27 (`dz-dashboard/docs/ACTIVE_WORK.md:105`) ·
the per-season config ledger (`ACTIVE_WORK.md:160`) · memories `bonus-scoring-fidelity`,
`league-settings-ledger`, `dst-yards-sacks-pipeline-gap`, `pre-2016-reconstruction-path`.
