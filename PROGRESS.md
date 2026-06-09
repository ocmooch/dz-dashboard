# PROGRESS.md — dz-dashboard (Phase 2)

The single source of truth for "where we are." **Read this first every session** instead of
re-scanning `analytics/` and `web/`. Keep it short and current — update it at every checkpoint
and at the end of every milestone. This file is what makes the plan/build/verify split cheap.

How to use it (see `CLAUDE.md` + `.claude/skills/milestone-session`):
- At session start, read this, then the one `P{N}` row in `docs/09_ROADMAP.md`, then the plan
  (`docs/plans/P{N}-*.md`) if one exists. Stop there — don't browse the tree.
- At session end / checkpoint, update **Current state**, **Next**, and **Files that matter now**.
- Historical fix-pass and audit narrative lives in `CHANGELOG.md`.
- **Aggregated records:** all finished work → `docs/archive/COMPLETED_WORK.md`; all remaining /
  in-progress work, blockers, and open decisions → `docs/ACTIVE_WORK.md`.

---

## Current state

- **Phase 2 implemented app features are functionally complete.** Roadmap milestones P0–P11 are
  shipped. P11 now includes committed Chromium/Linux visual-regression baselines, and CI runs the
  full Playwright suite (journeys plus visual snapshots). The Playoffs/Bracket view from F2.3
  is now landed locally as a caveated backend endpoint plus `/bracket` page: it renders proven
  post-regular-season games and does not infer a bracket tree.
- **League-history product slice landed locally.** Added read-only `/v1/league/overview`,
  `/v1/league/timeline`, `/v1/league/eras`, `/v1/league/stories`, and `/v1/league/managers`
  endpoints backed by `ff_dashboard.analytics.league_history`. The SPA now exposes top-level
  Seasons, Rules & Eras, Stories, and About Data navigation, with Home linking into the league
  archive. Accuracy pass now keeps the league at the active standings-backed 12-team size,
  caveats inactive/artifact team rows, and renders concrete change details for scoring rules,
  schedule length, roster/RES slots, waiver/FAAB, standings tiebreakers, manager churn, and
  source/provenance gaps.
- **Season-aware (period-correct) team names landed locally.** `analytics/historical_team_names.py`
  recovers the NFL.com season/slot name keyed by `(season_year, team_abbrev)` and
  `period_team_name()` overrides the post-merge canonical `team_name` on season-scoped surfaces
  (player ownership timelines). Falls back to the stored name when the slot/year is unknown.
- **Player scoring DNP/bye zero-week fix landed locally.** `/v1/players/{id}/scoring` now unions
  reconstructed scored rows with authoritative NFL.com roster points when available, so proven
  0-point inactive/injury/bye weeks render as zero bars with reason indicators instead of
  disappearing from the weekly chart. Real-DB spot check: player 11827 / 2025 now includes weeks
  5–12 as zero-point reasoned weeks, with week 9 marked bye.
- **Deferred product decisions resolved (Q10–Q13); team avatars built (Q11) — landed locally.**
  Q10 dark-only, Q12 laptop-first, Q13 no-exports settled at default (doc-only, reversible). Q11
  ships team logos from the DB: read-only binary `GET /v1/teams/{team_id}/avatar` streams from
  Phase 1's on-disk asset store (`ASSETS_ROOT` setting; `assets_root` on `app.state`), 404ing
  cleanly to a monogram fallback; `Chip` gained `avatarUrl`, wired across team chips. Owner photos
  remain a true source gap (0 rows; F-06). No contract change. Plan:
  `docs/plans/deferred-product-decisions.md`. Real-DB spot check passed (team 1 logo streams).
- **fix-pass P6 — MERGED, PR #40.** Shipped backend helpers/endpoints for
  standings luck/all-play, manager consistency, player insights, box-score enrichment, and revised
  all-play-aware power. Frontend uses shared season phase, re-curates Home, adds
  player/manager/standings insights, records trophy filtering, draft value filters + drill-down
  focus, power all-play methodology, and richer box-score player rows. **Full gate green** (backend
  pytest 213 + ruff + mypy; frontend gen:api no-drift + typecheck + Vitest 139; SPA production
  build). Real-DB verification on 2026-06-07: the two new insight endpoints
  (`/v1/players/{id}/insights`, `/v1/seasons/{id}/standings/insights`) plus box-score, power, and
  owners return honest `available`/`reason` payloads with no 500s, and the built SPA serves every
  P6 deep link. (No `lint` script exists in `web/`; typecheck is the TS gate.)
- **fix-pass P4 (Transactions, roster-diff tier) — MERGED, PR #35.** F-37 tier 1 shipped:
  `derive_roster_moves(session, team_id)`, additive
  `GET /v1/teams/{team_id}/roster-moves`, `RosterMove` / `TeamRosterMoves`, and the team-page
  **In-season moves** card. The existing transactions card is relabelled **Draft** because the
  real DB's `transactions` table is draft-only. Moves are not gated on `is_scored`; seasons with
  fewer than two roster snapshots return `available:false` with `roster_history_unavailable`.
- **F-53 is fixed upstream.** The danger-zone regen repaired corrupt week-1 roster snapshots.
  Real-DB verification on 2026-06-06 confirmed normal churn: team 184/2024 now returns wk1
  adds=2/drops=0 (was fabricated 68/67), and 2010 team 13 has period-correct week-1 players.
  No dashboard code change was needed after the regen.
- **fix-pass P5 (Frontend navigation & presentation fixes) — MERGED, PR #38.** Implemented:
  F-24 player-index contract cleanup, `WeekStepper` direct select, scrollable global search,
  rank-ordered timeline tooltips + 12-color ramp, team season navigation, unavailable box-score
  fallback links, manager latest-roster link, manager sort toggles, clearer rivalry labels, signed
  matchup margins, 12-column snake draft board, stats defaulting to season totals, standings final
  placement, and compact player ownership cards. Full gate is green; generated-client drift is
  clean; real-DB browser click-through completed on 2026-06-06.

## Next

- **The P1–P6 review-fixes program is complete** — all six dashboard passes are merged to `dev`.
  The remaining dashboard-side N2/F2.3 bracket decision is resolved locally by the caveated
  build. Next dashboard step is review/PR packaging.
- Next league-history expansion should consume upstream/manual identity and rules data when
  available: durable human manager overrides, roster-slot settings, full scoring-rule tables,
  playoff format metadata, and verified scoring mismatch classification.
- Remaining open product/data work is the **UP** (upstream / danger-zone) program: F-06 ownership
  succession, residual F-25 player identity cleanup, F-49 playoff/consolation metadata, and the
  F-27 trustworthiness sanity-check. Read-only spot check on 2026-06-07 shows F-37 tier 2 is now
  partly landed upstream (dated transaction rows with add/drop/waiver/trade/draft/lineup types);
  dashboard still renders the derived roster-diff tier and has not consumed exact transaction
  dates/FAAB details.
- **F-52 is RESOLVED upstream** by the danger-zone regen: the real DB now reports
  `status:completed` for 2010–2025 and `in_progress` only for 2026 (verified 2026-06-07). The P6
  season-phase helper derives phase from data rather than `seasons.status`, so no dashboard change
  is needed; a later pass could optionally trust `status` now that it is correct.

## Files that matter now

- F2.3 bracket local surfaces: `src/ff_dashboard/analytics/bracket.py`,
  `src/ff_dashboard/api/routes/seasons.py`, `web/src/features/bracket/BracketPage.tsx`
- League-history local surfaces: `src/ff_dashboard/analytics/league_history.py`,
  `src/ff_dashboard/api/routes/league.py`, `web/src/features/league/`
- Player scoring zero-week surfaces: `src/ff_dashboard/analytics/players.py`,
  `src/ff_dashboard/api/schemas.py`, `web/src/features/players/PlayerDetailPage.tsx`
- Docs/status touched for packaging: `docs/03_DATA_ACCESS.md`, `docs/04_ANALYTICS_MODEL.md`,
  `docs/05_API_CONTRACT.md`, `docs/07_PAGES_AND_VIEWS.md`, `docs/09_ROADMAP.md`,
  `docs/10_OPEN_QUESTIONS.md`, `PROGRESS.md`

## Open items / deviations

- Residual non-blocker from F-53 verification: 1–2 phantom **week-1-only** teams per season with
  duplicate/garbled names, present 2010–2018 and absent 2019/2023/2025. This is separate from the
  repaired roster-churn corruption and belongs with owner/team-identity research.
- League relevance = **ever-rostered only** (not "ever scored"): the pipeline scores the whole
  NFL, so "scored" is not a league-relevance signal.
- F-49 remains upstream: playoff/consolation metadata is insufficient to compute `made_playoffs`
  honestly for every season, so the dashboard returns `None` where the bracket cannot be inferred.

---

## Milestone tracker (P0–P11, from docs/09_ROADMAP.md)

| # | Milestone | Status | Plan | Notes |
|---|-----------|--------|------|-------|
| P0 | Prereqs & data-readiness gate | ☑ | — | data coverage note |
| P1 | BFF bootstrap (`/health`, `/v1/meta`, cache) | ☑ | — | `test_p1_bootstrap.py` |
| P2 | Analytics core + endpoints (standings, owners, h2h, records, players) | ☑ | — | fixture DB + known answers |
| P3 | Frontend bootstrap + design system | ☑ | — | tokens, primitives, gen:api drift check |
| P4 | Home + Standings + Manager profile | ☑ | — | + managers index/profile |
| P5 | Matchups + Box score (optimal lineup) | ☑ | — | authoritative NFL.com points |
| P6 | Rivalries + Records book | ☑ | — | deep-links to source matchup |
| P7 | Players + Stats explorer + Team page | ☑ | — | + players data-honesty audit |
| P8 | Draft views | ☑ | — | gap-label seasons w/o drafts |
| P9 | Power ranking + timelines | ☑ | — | shared chart wrappers |
| P10 | Global search + coverage/about + gap polish | ☑ | — | no fake zeros anywhere |
| P11 | Operations + docs + e2e/visual-regression | ☑ | — | Makefile/RUNBOOK/e2e + visual baselines in CI |

Status key: ☐ todo · ◐ in progress · ☑ done. Put the plan path in **Plan** once a PLAN
session writes `docs/plans/P{N}-{name}.md`.
