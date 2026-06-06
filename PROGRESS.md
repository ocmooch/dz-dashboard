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
- **fix-pass P4 (Transactions, roster-diff tier) — build done, unblocked, real-DB verified.**
  Branch `feature/fix-P4-transactions` has the dashboard work for F-37 tier 1:
  `derive_roster_moves(session, team_id)`, additive
  `GET /v1/teams/{team_id}/roster-moves`, `RosterMove` / `TeamRosterMoves`, and the team-page
  **In-season moves** card. The existing transactions card is relabelled **Draft** because the
  real DB's `transactions` table is draft-only. Moves are not gated on `is_scored`; seasons with
  fewer than two roster snapshots return `available:false` with `roster_history_unavailable`.
- **F-53 is fixed upstream.** The danger-zone regen repaired corrupt week-1 roster snapshots.
  Real-DB verification on 2026-06-06 confirmed normal churn: team 184/2024 now returns wk1
  adds=2/drops=0 (was fabricated 68/67), and 2010 team 13 has period-correct week-1 players.
  No dashboard code change was needed after the regen.
- **Everything else in the review-fixes program is merged or archived.** P1, P2, P2-redo, P3,
  F-51, and the players audit history are in `CHANGELOG.md`; completed plan docs are under
  `docs/archive/`. Active trackers remain in `docs/plans/`.

## Next

- Open the P4 PR from `feature/fix-P4-transactions` to `dev`. Optional before PR: one browser
  click-through of the team-page card; the SPA renders the verified BFF output verbatim.
- Then continue with **P5** and **P6** from `docs/plans/REVIEW_FIXES_ROADMAP.md`.
- Keep F-52 (`seasons.status` all `in_progress`) with danger-zone / upstream tracking.

## Files that matter now (fix-pass P4)

- `src/ff_dashboard/analytics/transactions.py` — `derive_roster_moves`: stint-model roster diff
- `src/ff_dashboard/api/schemas.py` — `RosterMove`, `TeamRosterMoves`
- `src/ff_dashboard/api/routes/teams.py` — `GET /v1/teams/{team_id}/roster-moves`
- `web/src/features/teams/TeamPage.tsx` — `RosterMovesCard`; "Draft" relabel
- `web/src/design-system/index.tsx` — `roster_history_unavailable` `DataGap` reason
- `web/src/lib/queryKeys.ts` — `teamRosterMoves(teamId)`
- `tests/test_p4_transactions.py` — known-answer + gap + not-gated + 404 tests
- `tests/conftest.py` — mav-2016 wk2 and mav-2015 unscored two-week roster scenarios
- `web/src/features/teams/team.test.tsx` — RosterMovesCard render/gap/empty paths
- `docs/04_ANALYTICS_MODEL.md` · `docs/05_API_CONTRACT.md` · `docs/07_PAGES_AND_VIEWS.md`
- `docs/plans/fix-P4-transactions.md` · `docs/plans/REVIEW_FIXES_ROADMAP.md`

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
