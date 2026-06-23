# Plan — DST deep-classification gap (the remaining 303 diverging rows)

**Status:** PLAN (2026-06-23). The relocation join fix landed (danger-zone `ea93b01`): DST diverging
500 → 303. This plan covers the two remaining classes, which need play-by-play and so were deferred.
Live DB is `../danger-zone/data/fantasy.db`; ground truth is `team_rosters.extra_data.nfl_com_points`;
the scoring is **correct** (an offline rule recompute reproduces stored `total_points` for all 303
rows with **0** mismatches) — every remaining gap is in the **source stat values**, not the engine.

## The census (fully offline, from `scratchpad/dst_final_census.py`)

Each diverging row classified by the minimal source change that reconciles our total to NFL.com,
disambiguated with the opponent's actual final score parsed from `extra_data.game_status`:

| Class | Rows | What it needs |
|-------|-----:|---------------|
| **TD undercount** (PA independently confirmed) | 155 | +1 or +2 uncredited defensive/ST TD (6 pts each) |
| TD-or-PA (ambiguous: +6 also = a 2-bracket PA move) | 21 | PBP to split |
| **points_allowed bracket** (final score fixes) | 74 | our derived PA is **too low**; opponent's final score is the right value |
| OTHER (need ±1/±2/±3/±5) | 53 | sacks / yards / residual one-offs |

Two clean, independent facts drive the plan:
1. The 74 PA rows **all** have `derived_points_allowed ≤ opponent_final_score`, and the final score's
   bracket is exactly the one that reconciles. We never over-charge; we **under**-charge.
2. The 155 TD rows have `derived PA == final-score bracket` already (opponent scored no defensive/ST
   TD that game), so their only gap is the 6/12-pt TD — a real `def_tds`/`special_teams_tds` shortfall.

---

## Class A — points_allowed under-count (74 rows). Do this FIRST: lower risk, likely a *simplification*

**Root cause hypothesis (strongly supported offline).** `team_defense._index_fantasy_points_allowed`
derives points-allowed from a PBP scoring-delta walk that deliberately **excludes** opponent
defensive/ST return TDs and safeties from the charge (see `_score_counts_against_dst` + the
`test_points_allowed_excludes_opponent_defensive_touchdown` family). But `nfl_com_points` says NFL.com
**does** count those points: in all 74 rows the correct points-allowed is the opponent's full final
score, and `derived < final` by exactly a return-TD-sized chunk (e.g. 27 vs 34 = a 6+1 return TD+XP).
i.e. NFL.com's D/ST "points allowed" is simply **the opponent's final score**, and the exclusion logic
encodes an unverified theory the authoritative data now contradicts.

**Fix.** Drop the PBP exclusion override and source `points_allowed` from the opponent's final score
(the schedule score `build_team_defense_stats` already reads as the fallback). This is net code
**deletion** (`_index_fantasy_points_allowed`, `_score_counts_against_dst`,
`_is_special_teams_return_touchdown`, and the pbp plumbing into `build_team_defense_stats`).

**Verification before deleting (needs one PBP/network window).** Pull 3–5 of the 74 rows, confirm the
excluded score was an opponent defensive/ST TD and that `nfl_com_points` only reconciles with
final-score PA. If a counter-example appears (a row where the exclusion is genuinely right and NFL
agrees), keep the override but fix its over-exclusion instead.

**Risk / gate.** The only way this regresses a row is if some currently-passing row relies on the
exclusion (derived < final and NFL agreed with derived). Validate on a DB copy: re-ingest + re-score,
require **74 fixed and 0 currently-correct rows newly broken**. Update/remove the unit tests that
encode the exclusion theory.

---

## Class B — DST TD undercount (155 confirmed + up to 21 ambiguous). The genuinely deep one

**Root cause.** `_DEFENSE_COUNTING_MAP` sources `defensive_tds ← def_tds` and
`special_teams_tds ← special_teams_tds` from nflverse **team-stats** columns, which undercount real
defensive/return/blocked-kick TDs. Both rule keys score 6 pts, so for *scoring* the two buckets are
interchangeable — we only need the correct **count of non-offensive TDs scored by the team**.

**Fix.** Derive DST TD counts from PBP — `derive_dst_td_counts(pbp_rows) -> {(season,week,canonical_team):
n}` — and source the count from PBP instead of the team-stats columns. Reuse the per-play
classification already proven in `_score_counts_against_dst` (it already separates offensive vs
defensive vs ST-return TDs for the points-allowed path) rather than the naive `touchdown==1 AND
td_team==defteam`.

**The trap (why a naive recount "fixes ~100 but breaks ~45").** A bare `td_team==defteam` over-counts:
- **Defensive 2-point-conversion returns** carry a TD-ish flag but are worth 2, not 6 — exclude
  (`two_point_conv_result`/`defensive_two_point`).
- **Muffed punt/kickoff recovered in the end zone by the kicking team** — `td_team` is the team on
  defense-of-the-return; classify by play context, not raw possession.
- **Laterals / multi-segment returns** can double-count one score.
- Some `def_tds` the team already has correct — the recount must **replace with the right count**, not
  add, and only where it moves the row toward `nfl_com_points`.

**Gate.** Same copy-first, zero-regression discipline as `backfill_fumbles_lost.py`: derive counts,
re-score on a copy, require net-positive with **0 rows newly broken**. If careful classification still
breaks any row, fall back to row-level guarding (apply only where it closes the gap to
`nfl_com_points`). The 21 ambiguous rows resolve naturally once the count is correct (PA already
confirmed for the 155).

---

## Mechanics (shared with the relocation fix)

- Crawler fixes go in `crawlers/nflverse/team_defense.py`; unit-test offline against hand-built
  PBP/schedule rows (the `tests/unit/test_team_defense.py` `_pbp_score` helper is ready).
- The live re-apply reuses the `scripts/backfill_dst_relocation_stats.py` pattern: re-run
  `run_team_defense` for all seasons + `rescore_seasons`, on a **copy first**, backup the live DB.
- **Blocker:** both need a network window to re-load nflverse PBP (cache mode is MEMORY — nothing
  persists between runs). The crawler logic + unit tests can be written and the offline audit
  (`scratchpad/dst_final_census.py`, `dst_attribute.py`) re-run without network; only the live
  re-ingest needs github reachability.

## Sequencing

1. **Class A (points_allowed)** — verify the final-score hypothesis on 3–5 rows via PBP, simplify the
   derivation, copy-validate (74 fixed / 0 broken), ship. Smallest, safest, likely a code deletion.
2. **Class B (DST TD recount)** — write `derive_dst_td_counts` with careful classification, copy-validate
   against the 45-break risk, ship. Expect ~176 rows fixed.
3. Re-census; the residual ~53 OTHER rows (sacks/yards one-offs) get a final offline pass.

**Done when:** DST diverging rows ≈ 0 (within the 0.1 verify tolerance) against `nfl_com_points`, the
green gate is clean, and the BFF coalesce becomes belt-and-suspenders rather than load-bearing for DST.
