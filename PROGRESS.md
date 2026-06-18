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

**The dashboard application is functionally complete and fully merged.** All P0–P12 milestones,
all P1–P6 review fix-passes, and every post-roadmap product slice are merged to `dev` and promoted
to `main`.

**In progress (2026-06-18):** `feature/draft-impact-model` builds the deferred "Part C" of the
draft genuine-zero work (#85): a composite **draft impact** = `value × cost_weight ×
opportunity_weight` that ranks steals/busts by more than raw points-over-expected. PLAN is
`docs/plans/P-draft-impact-model.md`. New reusable primitive `analytics/weighting.py`
(`weighted_impact` + `positional_weight`); `analytics/draft.py` gains tunable weight constants
(`COST_FLOOR`/`COST_CURVE`/`OPP_BENCH_WEIGHT`/`OPP_IR_WEIGHT` — an editable proposal), a
`_drafted_roster_weeks` helper (distinct bench/IR weeks from `team_rosters`), a pure
`_pick_impact` scorer, and `draft_value()` ranks steals/busts by impact (records book stays on raw
value by decision). Opportunity cost amplifies busts only and degrades honestly to
`value × cost_weight` when roster history is missing; `impact` is null iff `value` is. API:
`ImpactComponents`/`ImpactWeights` + `impact`/`impact_components` on `DraftPick`,
`impact_definition`/`weights` on `DraftValue`; client regenerated. Frontend: `ImpactTag` (headline
impact + secondary value + breakdown tooltip) on the steal/bust leaderboard. Gate green: backend
423 tests + ruff + mypy; frontend 185 tests, typecheck, `gen:api` drift in sync. **Next:** manual
click-through on the real DB (Cruz vs Gordon ordering) in a VERIFY session, then PR to `dev`. The
weights are an editable proposal — the user may tune them before the PR.

**In progress (2026-06-18):** `feature/matchup-superlative-flags` now uses a data-calibrated
60-point blowout threshold. Across 1,501 completed 2010–2025 matchups, the prior 40-point cutoff
flagged 27.0% of games; 60 points is approximately the historical 90th percentile and flags
10.6%, with similar rates across eras and regular-season/playoff games. Boundary coverage pins
60.0 as inclusive and rejects 59.99 and the retired 40-point cutoff.

**VERIFIED (2026-06-18):** the residual NFL.com source-identity misassignment class is repaired
across Phase 1 + dashboard observability. An authenticated sweep of all 2010–2025 draft and
transaction pages identified **34 true external-ID ownership mistakes** (excluding aliases,
renames, and legitimate position evolution). The reviewed upstream ledger re-homes NFL.com
rosters/transactions/availability, transfers IDs, seeds overrides, and recomputes spans
idempotently; the live DB repair completed from a timestamped backup and the maintained strict
audit now reports **0** mismatches. Resolver hardening rejects impossible direct-ID matches and
ambiguous abbreviated fuzzy matches. `/v1/meta/coverage` now exposes source-identity mismatch
diagnostics and Coverage & About reports the verified state. Live checks: 2016 pick 8 =
Lamar Miller/RB/158.0 regular-season points; pick 12 = Adrian Peterson/RB/7.7; Rob’s team
transaction feed names Lamar Miller; invalid unscored defensive-position draft picks = 0.
Full verification: Phase 1 pytest/ruff/format/mypy green; dashboard backend **387** tests plus
ruff/format/mypy/write-safety; frontend **179** tests, typecheck, production build, and regenerated
OpenAPI client.

**VERIFIED (2026-06-17):** `feature/bff-weekly-division-standings` supersedes the narrow
dead-conferences raw-SQL repair with BFF-owned weekly historical division standings. PLAN is
recorded in `docs/plans/bff-weekly-division-standings.md`: a reviewed NFL.com 2010–2019 division
artifact, exact matchup-derived weekly division records, source-ranked completed-season tables,
synchronized Record-lens week navigation, stacked historical tables, and full backend/component/
e2e/visual verification. The authenticated source capture is normalized and pinned (120 rows);
artifact validation, weekly analytics, mapping gaps, API query/schema, generated client, stacked
Record-lens UI, synchronized week requests, fixture-only e2e divisions, and backend/component/e2e
coverage are implemented. Full gate green: backend pytest **387**, ruff check/format, mypy, and
write-safety; generated API no-drift; frontend typecheck + **176** Vitest tests; **15** Playwright
journey/visual tests. Authenticated read-only source audit passes all ten seasons. Real-DB
early/middle/final inspection confirms complete 12-team tables and rank semantics for 2010, 2011,
2018, and 2019, with 2020 consistently ungrouped. **Post-review fixes:** historical division-query
failures now own a visible retryable error state, and a stale URL week is normalized when switching
to a shorter season (for example 2010 W14 → 2011 W13). Frontend gate remains green at **178**
Vitest tests plus the historical Playwright journey. **Ready to PR → `dev`.**

**In progress (2026-06-17):** `feature/teams-menu-and-page-refinements` surfaces the team pages and
reshapes their content. New top-level **Teams** nav → `TeamsIndexPage` (a flat `/v1/teams` index,
backed by `owners.teams_index()` reusing the standings/owner-season helpers) grouped collapsibly
**By season** (current season open by default) or **By owner**. Team page: the schedule gains a
horizontal W/L `ResultTimeline` (green/red cells, postseason set off by a subtle "PLAYOFFS" divider
+ accent ring) and its list collapses to one line per game; the redundant Transactions + "Roster-diff
fallback" cards merge into **one** compact, collapsible feed (acquisitions only — backend
`team_transactions` now drops `lineup_change`/`setting_change`), with the actor/device `notes`
suppressed and the derived roster-diff used only when no exact log exists, behind a single clear
"derived" flag. **Follow-up refinements (2026-06-17):** a short week's roster now pads up to the
team-season's usual size with dashed empty slots (`team_roster` → `is_empty`, derived from
snapshots not settings) instead of a note — the nearby transactions explain the drops; bench/IR are
never capped (the extra-bench-from-dropped-starter case renders in full). The transactions feed is
grouped into collapsible weeks (latest open; draft = its own week-0 "Draft" bucket; includes
pre-week-1 moves). Week-end snapshot semantics + variable bench documented in
`docs/03_DATA_ACCESS.md` and the `roster-snapshot-semantics` memory. Full gate green (backend 374,
frontend 172, typecheck, ruff, mypy, build) + manual click-through (team 175 wk17 shows 9 + 6 dashed
slots; wk17 drops sit right beside them). **PR #80 open → `dev`.**

**In progress (2026-06-17):** `feature/power-into-standings` retires `/power` as a top-level space
and folds it into **Standings** as a `?lens=power` toggle (`Tabs`) with a `WeekStepper` so power is
viewable for any week of any season — the backend already supported `through_week`, so this was
frontend-only. The Power table/hooks are extracted to a reusable `web/src/features/power/`
(`PowerTable.tsx`, `usePower.ts`); the routed `PowerPage` is gone and `/power` redirects to
`/standings?lens=power`. Playoffs gains a read-only "Power at playoff entry" snapshot. The model
math is unchanged (still the documented 0.40/0.25/0.20/0.15 z-score blend); only the explainer was
reframed to be honest that it is a points-dominant lens, not a forecast. **Ready to PR → `dev`.**

**In progress (2026-06-16):** `feature/data-coverage-matrix-dashboard` implements the dashboard
side of the Data Integrity & Coverage program from `docs/handoffs/`: a PLAN artifact
(`docs/plans/data-integrity-coverage-program.md`), `/v1/meta/coverage`, projection feed-cell
coverage for box scores, and interim identity-split detection. The matrix separates relevance
from feed coverage, emits reason codes, and counts unresolved cross-source player splits without
unioning stats/injuries in the dashboard. Fixture coverage now includes one covered projection
cell and one same-name roster/stats twin; contract tests pin both. The originating projection-gap
class now renders `DataGap` for feed-absent projection/value cells instead of bare dashes. The
anti-whack-a-mole rule is recorded in `docs/08_TESTING_STRATEGY.md`, and `docs/03_DATA_ACCESS.md`
points at `/v1/meta/coverage` as runtime truth. **VERIFIED (2026-06-16, Unit A):** full gate green
— backend pytest 369, ruff, mypy, write-safety clean; frontend `gen:api` no-drift, typecheck,
vitest 167 — plus real-DB click-through: `/matchups/1823` (2017 W7) renders all starters
`projection_available=false, reason=projections_not_captured` (Mike Williams pid=1032 DNP), and
`/matchups/193` (2025 W1) renders 9/9 starter projections + deltas. **This branch is ready to PR →
`dev`.** The program is re-cut into 5 single-repo units tracked in `docs/ACTIVE_WORK.md` §0 (the
single cycle-state source; the `docs/handoffs/*` checkboxes are reference-only). Unit A = this
branch; Units B/C (upstream crosswalk + identity-aware ingest), D (dashboard consume), and E
(projections-source investigation) remain.

Follow-up (same date): Units B/C/D/E were completed across `../danger-zone` and this dashboard.
The live DB is migrated to `player_identity_links`, seeded with the high-confidence Mike Williams
link `25239 -> 1032` plus documented no-link decisions for the other 17 duplicate-name triage
groups, and nflverse/Sleeper ingest maps now resolve linked members to the canonical player. The
Sleeper projection backfill populated every completed-season regular-week cell through 2025
(214/214 cells, no missing cells). Dashboard analytics now consume canonical clusters for box
scores, team rosters, player scoring, player insights, and unresolved-split detection. Live
verification: `/matchups/1823` Mike Williams renders on roster id `1032` with `league_points=0.0`,
`projection=0.0`, `projection_available=true`, and the coverage matrix reports
`identity_split_candidate_count=0`; W7 still correctly has no injury report row.

**Prior (2026-06-16):** `feature/player-flag-data-gap-cleanup` fixes a false-positive
class in the per-player `DATA` "roster drift" badge. The badge fires when the W-N snapshot shows
a player on a team but transactions don't *add* him until a later week. The acquisition scan in
`_roster_data_context_from_transactions` (`analytics/matchups.py`) required `direction == "in"`,
but `draft` rows carry `direction == "add"` (effective_week 0) — so a player **drafted** by the
team (legitimately on the W1 roster) who was later dropped and re-acquired via waiver/FA looked
like a brand-new late addition and got a red badge. Fix = count `direction in {"in","add"}` so the
W0 draft is the first acquisition. Empirical DB-wide scan (real `fantasy.db`): **800 box-score
rows** were false positives (all drafted-then-re-added, snapshot side correct, badge side wrong);
the fix clears every one (matchup 195 went 5→0 DATA badges — Dak Prescott, Keon Coleman, Evan
Engram, Rhamondre Stevenson, Washington DEF). **39 rows remain genuinely flagged** and all fall in
**2010 weeks 2–8**: there the in-season transaction log is missing (draft at W0, then *no*
add/drop/lineup txns until W6), so an early-season pickup that persisted has no acquisition row
before its W6+ first add — the history roster is right, the transaction log is incomplete. Those
39 are left flagged for upstream review (see Open items). BFF-only; SPA unchanged. Regression
tests added in `test_p5_matchups_unit.py` (drafted-then-re-added → no badge; un-drafted late add →
badge kept).

Same branch — **retired the DATA badge's second branch (slot conflict).** It fired when the
snapshot `roster_slot` disagreed with that week's `lineup_change` `to_slot`, but moving a player
between starting slots and the bench is routine, allowed lineup management — he never entered or
left the team, so it's not a data-integrity problem. DB-wide audit: 40 firings, **38 pure
start/bench juggling**, only 2 touched IR/RES. Worse, the flag *short-circuited* `_score_context`,
so the 2 IR/RES cases got a misleading "roster drift" message instead of their real reserve
context. Removed the branch (and the now-unused `roster_slot` param); the genuine IR/RES case is
owned by the existing reserve-eligibility path (slot in `IR_SLOTS`). Verified on the 2 real cases:
Nick Chubb m2200 → "Bye" (accurate), Ken Johnson m2053 → "RES" reserve context (accurate). Net:
DATA now fires only on genuine team-membership drift (branch 1).

**Prior (2026-06-16):** `feature/player-status-played-guard` suppresses NFL.com
current-state-drift `player_status` badges. NFL.com stamps a player's *current* roster status
onto historical weeks, so the box score showed IA/IR/SUS on players who clearly played and
scored that week (m193: IR×26, IA×22, SUS×1). New `analytics/player_status.py`
(`should_suppress_status` / `is_compatible_with_play`) gates `_score_context` and
`_reserve_eligibility_status` in `analytics/matchups.py`: an *incompatible* availability/roster
status (IA/IR/SUS/… — everything but the game-time Q/D/P designations) is dropped whenever the
player played (real nflverse stat line, an organic 0 included, or a positive league score).
Genuine DNPs keep their badge (honest 0 explanation). BFF-only fix — no schema change, SPA renders
only `context_label`; team page reads the separate injury-report table, unaffected. Verified on
m193: Q kept (Purdy/McCarthy), IA/IR dropped on all 8 scorers, IR kept on the genuine 0 (Lloyd).
This is §2 of the same drift class as the audit-snapshot fix below. The Phase-1 root fix (stop
storing current-status on history reconstructs) was implemented in `../danger-zone` PR #47.
Optional cleanup was run 2026-06-16: `reconstruct_lineups(..., year=2025, weeks=[1])`
rewrote 187 rows with 0 fetch failures; 2025-W1 history rows now have zero
`player_status` / `player_status_label` keys while keeping game status and NFL.com points.

**Prior (2026-06-15):** `feature/matchup-context-clues` fixes matchup box-score context
for unusual player states. The BFF now emits `context_label` / `context_detail` plus roster
status, NFL opponent/game status, and reserve eligibility context; the SPA renders DNP vs Out
accurately and shows non-zero reserve-slot scores as points plus a concise flag.

Polish (same branch): per-player `DATA` "roster drift" was firing on ~every player of an
**all-`audit`-snapshot week** (e.g. 2025-W1 / matchup 193, where the whole week is a
reconstructed roster audit, not a live capture). That is systemic, not player-specific, so we
now detect a reconstructed week (`_is_reconstructed_week`: every known `snapshot_kind` is
`audit`), **suppress the per-player DATA badges**, and surface **one team-level caveat**
(`BoxTeam.roster_reconstructed` / `roster_reconstructed_note`, rendered as a banner above the
lineup). A reserve-slot player *credited with points* is also no longer escalated to an `INJ`
badge (it implied an injury the data doesn't prove — Nabers/Hunter on m193); it stays `RES`.
Net for m193: from ~25 red DATA badges down to one banner per team + only the genuinely
player-specific flags (DNP / RES).

Full resolution (same branch): the audit-snapshot drift is a **class** (any week whose only
`team_rosters.snapshot_kind` is `audit` — a non-authoritative live capture stamped onto a week
slot, never superseded by `history`), not a one-off. The live DB has it on **2025-W1 and
2026-W1** (all 12 teams each). Detection is now centralized in `analytics/roster_snapshots.py`
(`snapshot_kind` / `is_reconstructed_week` / `reconstructed_note`) and every per-week roster
consumer honors it:
- **Box score** — one team-level banner; per-player DATA suppressed (as above).
- **Team page roster** — `team_roster` emits `roster_reconstructed` + note; `TeamPage` renders
  the same banner (the WeekStepper can land on an audit W1).
- **Roster-moves** (`derive_roster_moves`) — reconstructed weeks are **excluded from the
  week-over-week diff** (reported in `reconstructed_weeks`); previously an audit W1 baseline
  fabricated a phantom churn burst at W1→W2 (~15 fake adds/drops per 2025 team — verified gone).
- **Observability** — `scripts/audit_reconstructed_roster_weeks.py` (read-only, `--strict`)
  lists every reconstructed cell and flags those backing a live matchup; run after each ingest.

The Phase-1 **prevention** fix (stop an `audit` capture from ever being a week's sole
authoritative roster) is a separate `../danger-zone` change, handled on its
`feature/matchup-player-status-context` branch.

Recently landed branches:

- **#61** rivalries-insights — five league-wide rivalry insight bands + `GET /v1/rivalries/insights`.
- **#62** seasons league-changes — full auditable classifier (`analytics/league_changes.py`),
  nothing dropped; 3-tier Rules & Eras display.
- **#63 / #64** baseline gate debt — stale matchups tests removed, conferences `mypy`/`ruff`
  silenced, e2e + format debt cleared. **Gate is green.** (See Open items: the conferences
  *feature* is still silently dead at runtime even though its types are silenced.)
- **#65** injury enrichment — shared `analytics/injuries.py`; `InjuryBadge` on box score + roster.
- **#66** engagement / rivalries-strength — Standings "Robbed & Blessed" callouts + Manager-profile
  "Your Story" band (`analytics/owner_story.py`). The per-manager epithet proposal was presented
  but **not retained** (12/12 managers earned one → failed the "earned, not noisy" bar).
- **#67** matchup zero-status — team-roster scoring shares box-score zero semantics; read-only audit
  helper `scripts/audit_zero_score_gaps.py`; live run found 0 unexpected zeroes / 0 missing DST rows.

The aggregate of all finished work is `docs/archive/COMPLETED_WORK.md`; the remaining open scope is
`docs/ACTIVE_WORK.md`.

## Next

All remaining work is tracked in **`docs/ACTIVE_WORK.md`**. In priority order:

0. **Data Integrity & Coverage program** (cross-repo heavy lift; new 2026-06-16). Structural fix
   for the recurring data-gap / wrong-`player_id` whack-a-mole. Three handoff prompts under
   `docs/handoffs/`: start at `00-data-integrity-program.md`, then `player-identity-resolution.md`
   and `data-coverage-matrix.md` (paramount). `docs/ACTIVE_WORK.md` §0.
1. **The UP (upstream / `../danger-zone`) program** — Phase-1 data/research, not dashboard PRs:
   F-49 playoff/consolation metadata, F-27 reconstructed-scoring trust check, F-25 player-identity
   residuals, F-37 FAAB, and F-06 ownership succession (⊘ blocked — needs a source ledger you
   supply). `docs/ACTIVE_WORK.md` §2.
2. **League-history expansion** (dashboard, last) — gated on the UP outputs (per-season config
   ledger). `docs/ACTIVE_WORK.md` §3.

## Open items / deviations

- **Historical divisions repaired and verified.** The presumed Phase 1 conference tables/columns
  do not exist in the live schema; the dashboard now owns the reviewed source artifact and returns
  exact weekly division tables. Branch is ready to PR.
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
