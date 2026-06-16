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

Sibling upstream branch `../danger-zone` → `feature/player-identity-crosswalk` adds the additive
`player_identity_links` crosswalk table, ORM model, and `player_identity_cluster()` read helper
with focused tests. This is not the full canonical identity fix yet: curation/seeding of the Mike
Williams-style links and ingestion-aware resolver behavior remain upstream work before the
dashboard should union canonical clusters for stats/injuries.

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
1. **Repair the silently-dead conferences feature** (dashboard, do first; see Open items). The gate
   is green but `analytics/conferences.py` returns empty for the entire 2010–2019 conference era.
   Fix = the raw-SQL rewrite `standings.py` already uses. `docs/ACTIVE_WORK.md` §6.1.
2. **The UP (upstream / `../danger-zone`) program** — Phase-1 data/research, not dashboard PRs:
   F-49 playoff/consolation metadata, F-27 reconstructed-scoring trust check, F-25 player-identity
   residuals, F-37 FAAB, and F-06 ownership succession (⊘ blocked — needs a source ledger you
   supply). `docs/ACTIVE_WORK.md` §2.
3. **League-history expansion** (dashboard, last) — gated on the UP outputs (per-season config
   ledger). `docs/ACTIVE_WORK.md` §3.

## Open items / deviations

- **Conferences feature is silently dead (functional, not a gate failure).** `analytics/conferences.py`
  still imports non-existent Phase-1 ORM models (`SeasonConference`, `Team.conference_id`), so
  `_CONFERENCE_MODELS_AVAILABLE` is `False` at runtime (verified 2026-06-15). Every season wrongly
  returns `no_conferences_this_season` and `conference_map()` (used by `analytics/bracket.py`)
  returns `{}` — the 2010–2019 conference era is invisible. The data is fine: `standings.py` already
  reads the same `teams` / `season_conferences` tables via raw SQL. **Fix:** rewrite
  `conferences.py` to use the same raw SQL. Full handoff: `docs/ACTIVE_WORK.md` §6.1.
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
