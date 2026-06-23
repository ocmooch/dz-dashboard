# Bonus-scoring fidelity — remaining unresolved issues (cold-start handoff)

**Companion to** `docs/plans/bonus-scoring-fidelity.md` (the original plan + its two Resolution
sections). Read that first for the full diagnosis and what shipped. This doc is the **fresh-session
entry point for the work that is still open** after the 2026-06-23 session.

---

## TL;DR — where we are

The bonus-scoring fidelity gap was split into a BFF (dashboard) layer and an upstream (danger-zone)
re-score. **Both shipped for everything cleanly resolvable.** Divergence of `player_stats_scored.total_points`
from the authoritative `team_rosters.extra_data.nfl_com_points`, over the 39,512 rostered player-weeks
that have both:

| stage | diverging rostered rows |
|---|---|
| start (pre-session) | **2635** |
| after long-TD backfill (offensive positive) | 652 |
| after fumbles-lost backfill (offensive negative) | **574** |

The remaining **574** are the genuinely hard cases. They break down as:

| class | rows | status |
|---|---|---|
| **DST / DEF** | ~500 | **unresolved — deep gap (this doc, §1)** |
| offensive sub-2pt precision / rounding (positive) | ~38 | won't-fix precision (§2) |
| offensive negative residual (2011 wk13 bad-data week + unattributable 2010 sack-fumbles) | ~36 | data-quality tail (§3) |

**Nothing here blocks the dashboard.** The BFF coalesce (`analytics/scoring.py`,
`coalesce(nfl_com_points, total_points)`) renders the correct number for every **rostered** week
regardless, because `nfl_com_points` is ground truth there. These issues only affect the *upstream*
`total_points` itself — i.e. **unrostered** weeks (no ground truth to borrow) and the eventual goal of
**retiring the BFF coalesce** (§4).

---

## 1. DST / DEF divergence (~500 rows) — the primary open issue

**Symptom.** ~500 rostered DST weeks where `total_points ≠ nfl_com_points`. Positive deltas dominate
(defense under-scored); ~108 are negative (over-scored). Dominant single delta is **+6** (~154 rows).

**Confirmed not stale raw.** Re-running the current team-defense build
(`crawlers/nflverse/team_defense.py:build_team_defense_stats`) reproduces the **stored** DST raw stats
exactly. So this is real **source-data shortfall** in nflverse's team aggregates, not an un-applied
build. (Contrast the long-TD/fumble fixes, which were stale-raw and cleanly back-fillable from PBP.)

### 1a. D/ST touchdown undercount (the +6 class)
NFL.com credits the D/ST 6 points per defensive **or** return TD. nflverse's `def_tds` +
`special_teams_tds` aggregates miss some of these, so each missing TD shows as a flat **+6** delta
(verified: SEA 2017 wk4 PBP=2 D/ST TDs vs stored 1; NO 2017 wk6 PBP=3 vs 2; KC 2017 wk4 PBP=1 vs 0).

**What was tried and why it's not shipped.** Counting `touchdown==1 AND td_team==defteam` from PBP and
overwriting `defensive_tds` (zeroing `special_teams_tds`) fixes ~100 rows **but breaks 45 currently-
correct rows** — the simple predicate misclassifies some plays (offensive fumble recoveries in the end
zone, muffed-punt edge cases, returns where `td_team`/`defteam` don't mean what you'd expect). A safe
fix needs **per-play TD classification** distinguishing: pure defensive TD (INT/fumble return) vs
special-teams return TD vs offensive recovery — only the first two are D/ST points.

**Recommended next step.** Build a tested `derive_dst_td_counts(pbp_rows)` (mirroring
`crawlers/nflverse/long_td_bonus.py`) that classifies each scoring play and emits per-(team, week)
`defensive_tds` and `special_teams_tds` separately, with a fixture (`tests/fixtures/sample_data/`) and
focused unit tests. Wire it into `build_team_defense_stats` (it already receives `play_by_play_rows`),
then re-run `run_team_defense` for 2010–2024 + rescore. **Validation:** the 45-broken-rows regression
must go to 0 against `nfl_com_points`.

### 1b. Missing `total_yards_allowed` / `points_allowed`
~228 divergent DST rows lack `total_yards_allowed` (and some lack `points_allowed`), so the
already-seeded yards/points-allowed bracket bonuses score nothing. These are **opponent/schedule join
failures**, concentrated on **relocations** (the DST player's current code, e.g. `LV`, vs the season-era
schedule code `OAK`; same for `SD`→`LAC`, `STL`→`LA`). See the `dst-relocation-ingest-bug` memory.

**Recommended next step.** Audit `_def_player_index` / `_index_schedule` / `resolve_def_team_abbrev`
(`crawlers/nflverse/`) for the relocation seasons; ensure the opponent-yards join resolves season-era
codes on both sides. Also re-confirm the **net-of-sacks** `total_yards_allowed` definition
(`team_defense.py:78-80` notes nflverse `passing_yards` is gross of sacks; NFL.com subtracts sack
yardage) — a systematic few-yard offset there can flip a bracket.

**Tracking.** This whole section is the long-standing `dst-yards-sacks-pipeline-gap` (memory) and
F-27's DST half.

---

## 2. Offensive sub-2-point precision residuals (~38 rows, positive)

Small positive deltas (mostly +0.1 to +1.7, several exactly +0.3) on offensive rows that already have
their long-TD bonus. These are **rounding / unit-precision** differences between nflverse-derived yards
and NFL.com's posted points (e.g. a 100-yard receiving bonus boundary, or yard-rate rounding). Examples:
Austin Collie 2010 wk1 +1.70; multiple +0.30. **Recommendation: won't-fix** unless a systematic boundary
bug is found — they are below any display-meaningful threshold and the BFF shows `nfl_com_points` anyway.
If pursued, check the milestone-bonus boundary handling (`engine._score_rule` flat-bonus `threshold_max`
inclusivity) against NFL.com on the exact boundary cases.

---

## 3. Offensive negative residual (~36 rows)

After the fumbles-lost fix, ~36 offensive over-counts remain:
- **2011 wk13 cluster** — a whole group of Saints/Lions players (Mark Ingram −13.8, Kevin Smith −11.1,
  Brees −4.36, Colston, Burleson, Stafford, …) over-counted. This is a **bad-data week**: nflverse
  weekly stats for 2011 wk13 are inflated/misattributed vs NFL.com. Needs a targeted source audit of
  that week (compare nflverse weekly vs PBP-summed vs NFL.com), not a scoring change.
- **Unattributable lost fumbles** — a few rows (e.g. Chad Henne 2010 wk7, −2.00) where NFL.com charged
  a lost fumble but PBP `fumble_lost`/`fumbled_1_player_id` doesn't attribute it (older-season sack-fumble
  attribution gaps). Could try `fumbled_2_player_id` / sack-fumble columns as a secondary source.

---

## 4. Cross-cutting: can the BFF coalesce be retired?

**Not yet.** The brief's end-state was "once upstream is authoritative, drop the BFF
`coalesce(nfl_com_points, total_points)`." That is safe only when **all** rostered rows match within the
verify tolerance. With ~500 DST rows still divergent, the coalesce must stay. Re-evaluate after §1 lands.

Also unverified: the **per-season scoring rules are seeded identically across all 16 seasons** (51 rules
each). The fixes this session were data-shaped (missing PBP-derived stats), so uniform rules were *not*
implicated — but the league's NFL.com settings did change over history (see
`docs/archive/seasons-league-changes-inventory.md` / the `league-settings-ledger` memory). Before
retiring the coalesce, confirm no season needs a different ruleset (e.g. PPR/TD-value era changes) by
checking whether any *non-DST, non-fumble, non-long-TD* residual correlates with a season boundary.

---

## 5. Cold-start anchors (so a fresh session needn't re-derive)

**Repos.** dashboard `/home/mainuser/dz-dashboard` (branch `feature/bonus-scoring-fidelity`);
pipeline `/home/mainuser/danger-zone`. Live DB: `danger-zone/data/fantasy.db` (the repo-local
`dz-dashboard/data/fantasy.db` is a 0-byte stub — use `DATABASE_URL` to point at the danger-zone copy).

**What shipped this session (all idempotent, validated on a copy before live):**
- dz-dashboard: `src/ff_dashboard/analytics/scoring.py` (+ coalesce/rostered-ever wired into
  `stats.py`, `players.py`, `matchup_flags.py`, `draft.py`, route `players.py`); fixture canary in
  `tests/conftest.py`; tests in `tests/test_fixp1_stats.py`, `tests/test_p2_endpoints.py`.
- danger-zone: `scripts/backfill_long_td_bonus.py`, `scripts/backfill_fumbles_lost.py`.
- DB backups: `danger-zone/data/fantasy.db.bak-prelongtd-*`, `…bak-prefumble-*`.

**Re-run the two shipped backfills (idempotent — safe):**
```
cd /home/mainuser/danger-zone
uv run python scripts/backfill_long_td_bonus.py            # offensive long-TD; rescores
uv run python scripts/backfill_fumbles_lost.py             # offensive fumble penalty; rescores
```

**Reproduce the divergence census (read-only):**
```sql
WITH d AS (
  SELECT p.position pos,
         CAST(json_extract(tr.extra_data,'$.nfl_com_points') AS REAL) - pss.total_points delta
  FROM team_rosters tr
  JOIN seasons s ON s.year = tr.season_year
  JOIN player_stats_scored pss
       ON pss.player_id=tr.player_id AND pss.season_id=s.season_id AND pss.week=tr.week
  JOIN players p ON p.player_id = tr.player_id
  WHERE tr.week>0 AND json_extract(tr.extra_data,'$.nfl_com_points') IS NOT NULL)
SELECT
  SUM(CASE WHEN ABS(delta)>0.05 THEN 1 ELSE 0 END) all_div,
  SUM(CASE WHEN pos='DEF'  AND ABS(delta)>0.05 THEN 1 ELSE 0 END) def_any,
  SUM(CASE WHEN pos!='DEF' AND ABS(delta)>0.05 THEN 1 ELSE 0 END) off_any
FROM d;   -- expect ≈ 574 / 500 / 74
```

**Canary (must stay true):** Vick `player_id=23907`, 2010 (`season_id=2`) wk10 `total_points = 63.32`.

**Engine / rules facts (already correct — do not re-seed):** `scoring_rules` carries every bonus
(yardage milestones, long-TD 40=+1 / 50=+3 stacking, fumbles_lost −2, DST brackets); the engine
(`scoring/engine.py`) applies them; bonuses fold into category totals (there is **no** literal `bonus`
key — the original "0 bonus rows" signal was false). The gaps are **missing raw stats**, not missing
rules.

**Validation gate (the brief's target, still not fully met):** for every rostered week,
`|total_points − nfl_com_points| ≤ 0.1`. Current: 574 rows exceed it (≈500 DST, ≈74 offensive tail).

## 6. Suggested ordering for the next session
1. **§1a DST TD classification** (biggest, ~100+ rows, needs a tested PBP deriver) — highest value.
2. **§1b DST relocation/yards joins** (~228 rows) — pairs naturally with 1a in one team-defense re-run.
3. Re-census; if DST is clean, **§4 retire the BFF coalesce** behind the verify gate.
4. **§3 2011 wk13** source audit (small, isolated).
5. **§2** precision tail — only if a systematic boundary bug surfaces.
