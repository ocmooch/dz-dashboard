# PROGRESS.md — dz-dashboard (Phase 2)

The single source of truth for "where we are." **Read this first every session** instead of
re-scanning `analytics/` and `web/`. Keep it short and current — update it at every checkpoint
and at the end of every milestone. This file is what makes the plan/build/verify split cheap.

How to use it (see `CLAUDE.md` + `.claude/skills/milestone-session`):
- At session start, read this, then the one `P{N}` row in `docs/09_ROADMAP.md`, then the plan
  (`docs/plans/P{N}-*.md`) if one exists. Stop there — don't browse the tree.
- At session end / checkpoint, update **Current state**, **Next**, and **Files that matter now**.
- Historical fix-pass and audit narrative lives in `CHANGELOG.md`.

---

## Current state

- **Phase 2 is functionally complete.** All roadmap milestones P0–P11 shipped and the tracker
  below is closed out.
- **fix-pass P6 BUILD is implemented on `feature/fix-P6-frontend-insights`.** Shipped backend
  helpers/endpoints for standings luck/all-play, manager consistency, player insights, box-score
  enrichment, and revised all-play-aware power. Frontend now uses shared season phase, re-curates
  Home, adds player/manager/standings insights, records trophy filtering, draft value filters +
  drill-down focus, power all-play methodology, and richer box-score player rows. Focused backend
  tests, ruff, mypy, frontend typecheck, and focused Vitest are green; VERIFY still needs the full
  gate and real-DB click-through.
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

- Start **P6 VERIFY** from `docs/plans/fix-P6-frontend-insights.md`: run the full green gate,
  confirm generated-client drift is expected/additive, perform the real-DB browser click-through,
  then mark findings/roadmap and open the PR.
- Keep F-52 (`seasons.status` all `in_progress`) with danger-zone / upstream tracking.

## Files that matter now (fix-pass P6)

- `docs/plans/fix-P6-frontend-insights.md` — BUILD plan
- `docs/plans/REVIEW_FIXES_ROADMAP.md`
- `docs/reviews/2026-06-in-browser-review.md`
- P6 page surfaces: home, players, records/rivalries, managers, draft, power, standings

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
| P11 | Operations + docs + e2e/visual-regression | ☑ | — | Makefile, RUNBOOK, e2e specs |

Status key: ☐ todo · ◐ in progress · ☑ done. Put the plan path in **Plan** once a PLAN
session writes `docs/plans/P{N}-{name}.md`.
