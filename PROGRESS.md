# PROGRESS.md — dz-dashboard (Phase 2)

The single source of truth for "where we are." **Read this first every session** instead of
re-scanning `analytics/` and `web/`. Keep it short and current — update it at every checkpoint
and at the end of every milestone. This file is what makes the plan/build/verify split cheap.

How to use it (see `CLAUDE.md` + `.claude/skills/milestone-session`):
- At session start, read this, then the one `P{N}` row in `docs/09_ROADMAP.md`, then the plan
  (`docs/plans/P{N}-*.md`) if one exists. Stop there — don't browse the tree.
- At session end / checkpoint, update **Current state**, **Next**, and **Open items**.
- Aggregated history lives in `docs/archive/COMPLETED_WORK.md` (done) and `CHANGELOG.md`
  (reverse-chron passes); all remaining/open scope lives in `docs/ACTIVE_WORK.md`.

---

## Current state

**The dashboard application is functionally complete and fully merged.** All P0–P12 milestones, all
P1–P6 review fix-passes, and every post-roadmap product slice are merged to `dev`; `dev` was
promoted to `main` at **v0.2.0** (2026-06-15). The work merged to `dev` since v0.2.0 (PRs #72–#94,
below) awaits the next `dev → main` promotion.

**In flight:** `feature/bonus-scoring-fidelity` — bonus-scoring fidelity, both layers (uncommitted).
*BFF (full):* new `analytics/scoring.py` centralises `authoritative_week_points()` =
`coalesce(nfl_com_points, total_points)` + `rostered_ever()`; applied to Stats top-scorers (moved out of
Phase-1 `queries` — no gen:api drift), season-totals, player insights, matchup monster-game flag, draft
impact (records was already compliant). Backend 452 pass, ruff/mypy clean, FE typecheck+test green, no
contract drift. *Upstream (offensive class, applied to the live DB):* the rules were already correct —
the real gap was 2010–2024 raw rows missing PBP-derived long-TD keys. `danger-zone/scripts/
backfill_long_td_bonus.py` merged them + re-scored → Vick 2010 wk10 = 63.32. Then
`backfill_fumbles_lost.py` fixed the offensive over-count class (nflverse weekly `fumbles_lost`=0 where
PBP shows a lost fumble → seeded -2 penalty never applied): offensive negatives 124→36. Combined
total diverging rostered rows **2635→574** (backups `data/fantasy.db.bak-prelongtd-*`,
`-prefumble-*`). *DST relocation join (2026-06-23, danger-zone `ea93b01`):* the schedule frame
keeps relocated franchises' **era** codes (SD/OAK/STL) while team-stats/pbp use **current** codes
(LAC/LV/LA), so the opponent join in `team_defense.py` silently dropped points_allowed/yards/sacks
for those games. Fixed by folding every frame's code through `nfl_teams.canonical_franchise` +
`scripts/backfill_dst_relocation_stats.py` re-ingest/re-score: **DST diverging 500→303**, total
diverging rostered rows **574→368** (backup `data/fantasy.db.bak-predst-reloc-*`; Vick 63.32
preserved). *DST missing-TD recount (2026-06-23, danger-zone `4677d10`):* nflverse's `def_tds`/
`special_teams_tds` columns undercount real return/recovery TDs, so `team_defense.py` now recounts
from play-by-play — `play_type` (kickoff/punt/field_goal) drives the special-teams half so
kickoff-return TDs (which carry `td_team==posteam`) aren't dropped, `td_team!=posteam` drives the
defensive half, and the count only ever *raises* the total. Validated on a DB copy (full re-ingest +
rescore, row-by-row diff): **DST diverging 303→127**, the whole TD (155) + TD_or_PA (21) classes
resolved, **0 regressions / 0 worsened**, then applied to the live DB. Remaining upstream:
**127 DEF/DST rows** — 79 points-allowed bracket-boundary (proven false-positives; changing PA breaks
correct rows like GB 2020 wk6, deliberately untouched) + ~48 small one-off residuals. See
`docs/plans/bonus-scoring-fidelity.md` §Resolution addendum (2026-06-23 DST).

**Prior in flight:** `feature/records-accuracy` — corrects the Records book against the post-fidelity data.
"Best player week" now uses authoritative `nfl_com_points` over **started** roster rows (Doug Martin
2012 wk9, not a whole-NFL reconstruction max), and the matchup records (blowout/narrowest/highest-
scoring) carry both sides' season-correct names. See CHANGELOG 2026-06-22. Gate green.

**Merged since v0.2.0 (PRs #72–#94)** — reverse-chronological, prose detail in `CHANGELOG.md` /
`docs/archive/COMPLETED_WORK.md`:

- **#94** 2022 Hamlin no-contest championship resolution — box score branches on the upstream
  `hamlin_substitute` flag (wk17-partial + wk19), matchup `resolution_note` banner, curated
  `league_event` in the timeline. Corrected champion = Smokin Doubs (see memory
  `hamlin-2022-championship-anomaly`).
- **#90–#93** FAAB suite — bid capture surfaced (`$0` = real free claim; `"$X FAAB"` pill), then the
  weekly **remaining-budget** view (`team_faab_budget()`, `/v1/teams/{id}/faab-budget`,
  `FaabBudgetCard`): $100 base + parsed mid-season credits, reproduces the 2022 +$37 refund.
- **#85–#89** draft suite — genuine-zero classification, opportunity-cost-weighted **draft impact**
  composite (`analytics/weighting.py`), integrity follow-up (canonical-identity scoring), query
  perf (cold ~24k q → ~167 q via cached history sweep + batched identity), fantasy-position taxonomy.
- **#82–#84** matchup superlative flags (60-pt blowout threshold), source player-identity integrity
  exposure, and **BFF-owned weekly historical division standings** (supersedes the dead conferences
  feature for 2010–2019).
- **#77–#81** Data Integrity & Coverage program (`/v1/meta/coverage`, self-explaining projection
  gaps, identity-split detection), handoffs, DATA roster-drift false-positive cleanup, visual
  baseline refresh.
- **#72–#79** CI prune fix, player context/status-drift guards, power-into-Standings lens,
  `/seasons`+`/rules` → one **Timeline** space, Teams nav + team-page refinements.

The aggregate of all finished work is `docs/archive/COMPLETED_WORK.md`; the reverse-chron pass
history is `CHANGELOG.md`; the remaining open scope is `docs/ACTIVE_WORK.md`.

## Next

**Planned, not started — Bonus-scoring fidelity.** Stats Top Scorers (and Home, Season Totals, player
Insights, draft impact, monster-game flag) drift because `player_stats_scored.total_points` omits NFL.com
scoring bonuses league-wide (Vick 2010 wk10 reads 58.32 vs the correct 63.32). Full diagnosis, owner
decisions, and cold-start build anchors are in **`docs/plans/bonus-scoring-fidelity.md`** (the open
validation half of F-27). Start a fresh BUILD session from that plan: step 1 is the BFF interim — move
`top_scorers` into `analytics/stats.py` with `coalesce(nfl_com_points, total_points)` + a rostered-ever
view filter so the canary reads 63.32. See memory `bonus-scoring-fidelity`.

Otherwise, no open dashboard work. All remaining items are tracked in **`docs/ACTIVE_WORK.md`**; in
priority order:

1. **The UP (upstream / `../danger-zone`) program** — Phase-1 data/research, not dashboard PRs:
   F-49 playoff/consolation metadata, F-27 reconstructed-scoring trust check, F-25 player-identity
   residuals (D1/D2/D3/D4), F-37 richer exact-transaction tier, and F-06 ownership succession
   (⊘ blocked — needs a source ledger you supply). `docs/ACTIVE_WORK.md` §2. *(The Data Integrity &
   Coverage program — dashboard Units A/D and upstream Units B/C/E — is complete and merged, #77.)*
2. **League-history expansion** (dashboard, last) — gated on the UP outputs (per-season config
   ledger). `docs/ACTIVE_WORK.md` §3.
3. **Phase 3** — early brainstorm only (NL "league historian" over an insight-primitive library);
   kept as a local working note, not committed and not a milestone. A PLAN session promotes it if
   chosen.

## Open items / deviations

- **Historical divisions repaired and verified (merged #82).** The presumed Phase 1 conference
  tables/columns do not exist in the live schema; the dashboard now owns the reviewed source
  artifact and returns exact weekly division tables. This closes the old "conferences feature
  silently dead" debt (former OPEN_QUESTIONS N6 / ACTIVE_WORK §6.1).
- **Phantom week-1-only teams (identity artifact).** 1–2 phantom week-1-only teams per season with
  duplicate/garbled names, present 2010–2018 and absent 2019/2023/2025. Separate from the repaired
  F-53 roster-churn corruption; belongs with owner/team-identity research (F-06).
- **2010 in-season transaction log starts at W6 (upstream gap).** 2010 has draft txns (W0) but
  the first add/drop/lineup/trade/waiver row is W6 — weeks 1–5 were never ingested. Effect on the
  dashboard: 39 box-score rows (2010 W2–W8) still carry the per-player `DATA` "roster drift" badge
  because their history-snapshot team membership has no corroborating acquisition txn before W6.
  The roster side is correct; the badge is honest-but-noisy on a known-incomplete window. Resolution
  pending upstream: backfill 2010 W1–W5 transactions in `../danger-zone`, or (dashboard) treat a
  season whose earliest non-draft txn week > 1 as a coverage gap and suppress the per-player badge
  there. Left flagged this pass per the investigation that landed `feature/player-flag-data-gap-cleanup`.
- **F-49 `made_playoffs = None`** where a bracket can't be inferred honestly — intentional until
  upstream playoff/consolation metadata lands (see `docs/ACTIVE_WORK.md` §2 F-49).
- **League relevance = ever-rostered only** (not "ever scored"): the pipeline scores the whole NFL,
  so "scored" is not a league-relevance signal.

---

## Milestone tracker (P0–P12, from docs/09_ROADMAP.md)

| # | Milestone | Status | Notes |
|---|-----------|--------|-------|
| P0 | Prereqs & data-readiness gate | ☑ | data coverage note (`docs/03_DATA_ACCESS.md`) |
| P1 | BFF bootstrap (`/health`, `/v1/meta`, cache) | ☑ | `test_p1_bootstrap.py` |
| P2 | Analytics core + endpoints (standings, owners, h2h, records, players) | ☑ | fixture DB + known answers |
| P3 | Frontend bootstrap + design system | ☑ | tokens, primitives, gen:api drift check |
| P4 | Home + Standings + Manager profile | ☑ | + managers index/profile |
| P5 | Matchups + Box score (optimal lineup) | ☑ | authoritative NFL.com points |
| P6 | Rivalries + Records book | ☑ | deep-links to source matchup |
| P7 | Players + Stats explorer + Team page | ☑ | + players data-honesty audit |
| P8 | Draft views | ☑ | gap-label seasons w/o drafts |
| P9 | Power ranking + timelines | ☑ | shared chart wrappers |
| P10 | Global search + coverage/about + gap polish | ☑ | no fake zeros anywhere |
| P11 | Operations + docs + e2e/visual-regression | ☑ | Makefile/RUNBOOK/e2e + visual baselines in CI |
| P12 | Player injury reports (Phase 1 + BFF + UI) | ☑ | Phase-1 upstream + BFF/UI merged (PR #53) |

Status key: ☐ todo · ◐ in progress · ☑ done.
