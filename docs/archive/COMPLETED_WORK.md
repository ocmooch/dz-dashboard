# COMPLETED_WORK.md — dz-dashboard (Phase 2 archive aggregate)

The consolidated, **archived** record of all finished development on dz-dashboard: shipped
roadmap milestones, merged fix-passes, completed audits, data-regeneration events, and the
findings/open-questions they resolved. This file is **append-mostly history** — once something
lands here it is done and does not move back to active.

- **Active / remaining work** lives in `docs/ACTIVE_WORK.md` (not archived).
- **Current state** snapshot lives in `PROGRESS.md`.
- **Per-pass narrative** lives in `CHANGELOG.md` and the archived plan docs indexed below.
- The detailed append-only build log for the review-fixes program is
  `docs/plans/REVIEW_FIXES_ROADMAP.md`.

Status convention used below: ☑ = done/merged/resolved.

---

## 1. Phase 2 roadmap milestones (P0–P11) — all shipped ☑

The 12 Phase-2 build milestones from `docs/09_ROADMAP.md` are complete. Phase 2 implemented
app features are functionally complete: a read-only FastAPI BFF, a generated-contract React
SPA, and the full view set.

| # | Milestone | Status | Notes |
|---|-----------|--------|-------|
| P0 | Prereqs & data-readiness gate | ☑ | data-coverage note; `docs/archive/P0_DATA_READINESS.md` |
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
| P11 | Operations + docs + e2e/visual-regression | ☑ | Makefile/RUNBOOK/e2e + committed Chromium/Linux visual baselines in CI |

Supporting ops shipped with P11: root `README`, `web/README.md`, `docs/PHASE2_RUNBOOK.md`,
`Makefile`, local service scripts (`scripts/dz-dashboard.service`, `scripts/cron.example`),
and full e2e/visual-regression specs (`e2e/visual.spec.ts` with committed baselines; CI runs
the full Playwright suite).

---

## 2. Review-fixes program (fix-passes P1–P6) — all merged to `dev` ☑

Executed against the 2026-06 in-browser review (`docs/reviews/2026-06-in-browser-review.md`,
48 findings F-01–F-48). These **fix-pass** numbers are distinct from the milestone numbers
above. The detailed append-only build log is `docs/plans/REVIEW_FIXES_ROADMAP.md`.

| Pass | Title | Findings resolved | PR | Archived plan |
|------|-------|-------------------|----|---------------|
| P1 | Analytics correctness, scoping & enrichment (incl. season-structure model) | F-32, F-22, F-31, F-10, F-12, F-23, F-17, F-13 | #30 | `docs/archive/fix-P1-analytics.md` |
| P2 | Data honesty & affordance precision (+ gap-validation harness) | F-16, F-35, F-26, F-33, F-48, F-43 | #31 + redo #34 | `docs/archive/fix-P2-honesty.md`; `docs/archive/fix-P2-post-regen-redo.md` |
| P3 | Search: scope, teams, hardening | F-44, F-45, F-47 | #32 | `docs/archive/fix-P3-search.md` |
| P4 | Transactions (dashboard roster-diff tier) | F-37 (tier 1) | #35 | `docs/archive/fix-P4-transactions.md` |
| P5 | Frontend: navigation & presentation fixes | F-34, F-36, F-05, F-24, F-07, F-15, F-46, F-14, F-11, F-40, F-30, F-04, F-28, F-02, F-42 | #38 | `docs/archive/fix-P5-frontend-fixes.md` |
| P6 | Frontend: composition, seasonality & insight enhancements | F-01, F-29, F-08, F-03, F-09, F-18, F-38, F-21, F-41 | #40 | `docs/archive/fix-P6-frontend-insights.md` |

**Highlights of what each pass delivered:**

- **P1 (PR #30):** per-season schedule model (config-driven), records era split, fantasy-week-capped
  season totals (dashboard-side `analytics/stats.py`, not Phase-1), owner-season result derivation,
  H2H cumulative margin + `closest_meeting` (typed schema), matchup close/blowout + entering-record
  fields. Close/blowout thresholds moved to backend flags. Real-DB confirmed a 2011 game can hold a
  team record (`lowest_team_score` 36.8).
- **P2 (PR #31, redo PR #34):** shared gap copy (`PRE2016_GAP_NOTE`), `season_unscored` /
  unscored-rostered player affordances, and the first coverage-integrity harness
  (`tests/test_coverage_integrity.py`, F-43). The redo rebased the harness off `is_scored` after the
  F-51 regen — it no longer assumes "player scoring absent pre-2016" and discovers scored seasons
  from rows.
- **P3 (PR #32):** league-scoped player search, NFL team/city/nickname expansion, fantasy team-name
  hits linking to managers, and hardening for LIKE wildcards, injection, regex metacharacters,
  scripts, and blank input. No `dangerouslySetInnerHTML` anywhere (React escapes by default).
- **P4 (PR #35):** `derive_roster_moves(session, team_id)` (stint-model diff over `team_rosters`),
  additive `GET /v1/teams/{team_id}/roster-moves` + `RosterMove`/`TeamRosterMoves` schema, team-page
  **In-season moves** card. Existing transactions area relabelled **Draft** (draft-only on the real
  DB). Not gated on `is_scored`; `<2` snapshots → `available:false` + `roster_history_unavailable`.
- **P5 (PR #38):** F-24 player-index contract cleanup (`scope`/`has_scored` removal), `WeekStepper`
  direct select, scrollable global search, rank-ordered timeline tooltips + 12-color ramp, team season
  navigation, unavailable box-score fallback links, manager latest-roster link + sort toggles, clearer
  rivalry labels, signed matchup margins, 12-column snake draft board, stats defaulting to season
  totals, standings final placement, compact player ownership cards.
- **P6 (PR #40):** backend helpers/endpoints for standings luck/all-play, manager consistency,
  player insights, box-score enrichment, all-play-aware power. Frontend shared season-phase helper,
  re-curated Home, player/manager/standings insights, records trophy filtering, draft value filters +
  drill-down focus, power all-play methodology, richer box-score player rows. Full gate green
  (213 pytest + ruff + mypy; gen:api no-drift + typecheck + 139 Vitest; SPA build).

**Program close-out:** all six dashboard passes merged to `dev`; the gap-validation harness is green;
`PROGRESS.md` reflects post-review state. The remaining open scope is the **UP** upstream program —
see `docs/ACTIVE_WORK.md`.

---

## 3. Post-roadmap product slices landed locally ☑

Shipped on `feature/season-aware-team-names` (commit `67acb5b`) and earlier feature branches,
beyond the original P0–P11 / P1–P6 scope.

- **League-history product slice.** Read-only `/v1/league/overview`, `/v1/league/timeline`,
  `/v1/league/eras`, `/v1/league/stories`, `/v1/league/managers` backed by
  `ff_dashboard.analytics.league_history`. SPA adds top-level Seasons, Rules & Eras, Stories, and
  About Data nav; Home links into the league archive. Keeps the league at the active
  standings-backed 12-team size, caveats inactive/artifact team rows, and renders concrete change
  details for scoring rules, schedule length, roster/RES slots, waiver/FAAB, standings tiebreakers,
  manager churn, and source/provenance gaps.
  Surfaces: `src/ff_dashboard/analytics/league_history.py`, `src/ff_dashboard/api/routes/league.py`,
  `web/src/features/league/`.
- **Season-aware (period-correct) team names.** `analytics/historical_team_names.py` recovers the
  NFL.com season/slot name keyed by `(season_year, team_abbrev)`; `period_team_name()` overrides the
  post-merge canonical `team_name` on season-scoped surfaces (player ownership timelines). Falls back
  to the stored name when the slot/year is unknown.
- **Player scoring DNP/bye zero-week fix.** `/v1/players/{id}/scoring` unions reconstructed scored
  rows with authoritative NFL.com roster points, so proven 0-point inactive/injury/bye weeks render
  as zero bars with reason indicators instead of disappearing. Real-DB spot check: player 11827 /
  2025 now includes weeks 5–12 as zero-point reasoned weeks, with week 9 marked bye.
  Surfaces: `src/ff_dashboard/analytics/players.py`, `src/ff_dashboard/api/schemas.py`,
  `web/src/features/players/PlayerDetailPage.tsx`.
- **F2.3 Playoffs/Bracket view (caveated).** Caveated `/bracket` route backed by
  `GET /v1/seasons/{id}/bracket` (`analytics/bracket.py`). Exposes only proven post-regular-season
  matchup rows grouped by week, with `available:false` / `bracket_unavailable` when none exist. Does
  **not** infer a bracket tree, advancement, or playoff berth. (F-49 source metadata remains
  upstream — see `docs/ACTIVE_WORK.md`.)

---

## 4. Players-view data-honesty audit (2026-05) ☑

- **Phase A:** made the player index league-relevant by default, enriched rows with rostered-season
  span and `has_scored`, collapsed ownership into spans, added explicit bio gap affordances.
- **Phase B:** added last-year-played, removed the unreliable nflverse active/retired UI signal,
  folded rostered spans onto Phase 1's `Player.first_rostered_season`/`last_rostered_season`.
- **B4:** confirmed the contamination guard after the danger-zone D5 fix — duplicate cross-team
  roster groups and home/away lineup intersections were 0 on the real DB.

Archived plan: `docs/archive/players-audit-dashboard.md`. (The upstream half of this audit is still
open — see `docs/handoffs/players-audit-danger-zone.md` and `docs/ACTIVE_WORK.md` §F-25.)

---

## 5. Data-regeneration events & resolved upstream findings ☑

The `danger-zone` / ff-pipeline `fantasy.db` was regenerated, resolving several blocking findings
with **no dashboard code change** (read-only boundary; the fixes were upstream).

- **F-50 ☑ (regen).** Real-DB 500s app-wide — `OperationalError: no such column:
  teams.team_avatar_asset_id`. ff-pipeline advanced to 1.2.0 (added `teams.team_avatar_asset_id` /
  `owner_avatar_asset_id`) but the on-disk DB predated the columns. Resolved by regenerating with the
  1.2.0 pipeline. Lesson: fixture tests can't catch it — the fixture DB is built from the live 1.2.0
  ORM, so only a real-DB run surfaces it. (See memory `stale-db-team-avatar-columns`.)
- **F-51 ☑ (regen → reframe).** The regen reconstructed pre-2016 per-player fantasy scoring:
  `player_stats_scored` now spans **2010–2025** (was a 2016–2025 window). The only normally-unscored
  season is the current/in-progress one. The dashboard pass removed stale pre-2016 gap copy,
  generalized the player-detail unscored-tenure predicate, and kept every gate data-driven on the
  per-season `is_scored` flag (never hardcode a year). Verified on the real DB.
- **F-52 ☑ (regen, confirmed in P6 VERIFY 2026-06-07).** Previously every `seasons.status` read
  `in_progress`; the real DB now reports `status:completed` for 2010–2025 and `in_progress` only for
  2026. The P6 season-phase helper derives phase from data rather than `seasons.status`, so it was
  already correct; no dashboard change needed.
- **F-53 ☑ (regen).** `team_rosters` week-1 was a corrupt/placeholder snapshot in every season
  2010–2025 (disjoint from wk0+wk2; 2010 wk1 listing modern players like Brock Purdy), which P4's
  all-week diff faithfully rendered as fabricated churn (e.g. 68 adds + 67 drops at wk1). The regen
  repaired wk1: wk1∩wk2 overlap is now 0.71–0.88 across all seasons, wk1 holds period-correct
  players. Real-DB verification: team 184/2024 (the original case) now returns wk1 2 adds/0 drops;
  2010 team 13 → wk1 5/5. No dashboard code change. (A residual phantom-team artifact remains — see
  `docs/ACTIVE_WORK.md`.)

---

## 6. Resolved open questions & build-surfaced issues ☑

From `docs/10_OPEN_QUESTIONS.md` — settled by the as-built system.

**Sign-off questions (Q1–Q7), all decided & built:**

| # | Question | Decision (as built) |
|---|----------|---------------------|
| Q1 | Data-access architecture | BFF reusing `ff_pipeline.repository`, read-only/WAL; analytics server-side; SPA pure presentation. |
| Q2 | Frontend stack | React 18 + TS + Vite + Tailwind + TanStack Query + React Router + Recharts + `openapi-typescript`/`openapi-fetch`. Hand-built primitives (no shadcn). |
| Q3 | Visual direction | "Danger Zone" HUD — dark instrument panel, afterburner-orange `#ff6a1a`, mono/tabular numerics. Saira Condensed / IBM Plex Sans / IBM Plex Mono. |
| Q4 | View priority | Built per default order, incl. Manager index/profile + caveated Playoffs/Bracket. |
| Q5 | Standings tiebreaker | Prefer reconstructed `teams.final_rank`; else wins→points-for with `rank_basis` + `tiebreak_caveat`. Old best-of-3 not re-derived. |
| Q6 | Power-ranking model | Z-score blend 0.5·PPG + 0.3·win% + 0.2·last-3-PPG; weights shipped in payload. |
| Q7 | Optimal-lineup definition | `analytics/matchups.py` optimal-lineup / points-left-on-bench from roster slot config; hand-solved unit test. |

**Build-surfaced issues resolved:**

- **N1 ☑** Manager index (`/managers`) + Manager profile (`/managers/{owner_id}`) composed against
  the `/v1/owners/*` endpoints; win% client-derived; record-only seasons render a `DataGap`.
- **N2 (resolved locally)** Playoffs/Bracket — caveated `/bracket` build (see §3).
- **N3 ☑** `/v1/home` composite dropped in favor of client-side composition of standings + records +
  power (SPA does orchestration only, no math). Docs 02/04/05/07 updated.
- **N4 ☑** Visual-regression baselines committed (Chromium/Linux); CI runs the full Playwright suite.

(Deferred questions Q8–Q13 shipped at their defaults and remain reversible; N5 upstream items remain
open — both tracked in `docs/ACTIVE_WORK.md`.)

---

## 7. Documentation consolidation events ☑

- **2026-06-06:** reconciled live docs with F-51; moved completed plans and historical snapshots into
  `docs/archive/`; moved the design handoff to `docs/DESIGN_HANDOFF.md`; condensed `PROGRESS.md`.
- **2026-06-07 (DOC-AUDIT):** reviewed plans/handoffs/roadmap/open-questions/reviews against code and
  read-only DB state. Confirmed P1–P6 complete and P11 visual-regression closed; recorded that UP is
  partially retired (dated typed transaction rows exist and are consumed; FAAB absent), F-49 still
  open, F-25 improved but residual.
- **2026-06-08:** split tracking into this archive aggregate (`COMPLETED_WORK.md`) and the active
  aggregate (`docs/ACTIVE_WORK.md`); moved merged fix-pass plans P4–P6 from `docs/plans/` into
  `docs/archive/` and updated the roadmap references.

---

## Index of archived plan / snapshot docs

- `docs/archive/PHASE2_KICKOFF.md` — original human kickoff
- `docs/archive/prerequisites.md` — P0 prerequisites
- `docs/archive/P0_DATA_READINESS.md` — data-readiness note
- `docs/archive/players-audit-dashboard.md` — players data-honesty audit (dashboard half)
- `docs/archive/fix-P1-analytics.md` … `fix-P6-frontend-insights.md` — merged fix-pass plans
  (P2 has both `fix-P2-honesty.md` and `fix-P2-post-regen-redo.md`)
