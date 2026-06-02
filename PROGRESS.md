# PROGRESS.md — dz-dashboard (Phase 2)

The single source of truth for "where we are." **Read this first every session** instead of
re-scanning `analytics/` and `web/`. Keep it short and current — update it at every checkpoint
and at the end of every milestone. This file is what makes the plan/build/verify split cheap.

How to use it (see `CLAUDE.md` + `.claude/skills/milestone-session`):
- At session start, read this, then the one `P{N}` row in `docs/09_ROADMAP.md`, then the plan
  (`docs/plans/P{N}-*.md`) if one exists. Stop there — don't browse the tree.
- At session end / checkpoint, update **Current state**, **Next**, and **Files that matter now**.

---

## Current state

- Branch: `feature/phase-2-dashboard` (cut from `dev`)
- Last milestone completed: **P? — <fill in>**
- Last commit: `<short sha + summary>`
- Gate status at last checkpoint: backend <green/red>, frontend <green/red/n-a>

> Bootstrapping note: confirm the real state with a *single* cheap pass —
> `git log --oneline -15` and `git grep -l "router" src/ff_dashboard/api/routes` —
> then fill the milestone table below once and maintain it by hand thereafter.

## Next

- **This session's mode:** <PLAN | BUILD | VERIFY>
- **Milestone:** P? — <name>
- **Immediate next step:** <the precise next action, e.g. "write analytics/power.py per docs/plans/P9-power.md, start with the test list">

## Files that matter now

List only the handful in play for the current step, so the next session opens those and
nothing else:

- `src/ff_dashboard/analytics/<x>.py`
- `tests/dashboard/test_<x>.py`
- `web/src/features/<x>/...`

## Open items / deviations

- <anything that diverged from the plan or a doc default; unresolved questions from docs/10>

---

## Milestone tracker (P0–P11, from docs/09_ROADMAP.md)

| # | Milestone | Status | Plan | Notes |
|---|-----------|--------|------|-------|
| P0 | Prereqs & data-readiness gate | ☐ | — | data coverage note |
| P1 | BFF bootstrap (`/health`, `/v1/meta`, cache) | ☐ | — | |
| P2 | Analytics core + endpoints (standings, owners, h2h, records, players) | ☐ | — | fixture DB + known answers |
| P3 | Frontend bootstrap + design system | ☐ | — | tokens, primitives, gen:api drift check |
| P4 | Home + Standings + Manager profile | ☐ | — | first end-to-end slice |
| P5 | Matchups + Box score (optimal lineup) | ☐ | — | needs P0 reconstruction |
| P6 | Rivalries + Records book | ☐ | — | deep-links to source matchup |
| P7 | Players + Stats explorer + Team page | ☐ | — | |
| P8 | Draft views | ☐ | — | gap-label seasons w/o drafts |
| P9 | Power ranking + timelines | ☐ | — | shared chart wrappers |
| P10 | Global search + coverage/about + gap polish | ☐ | — | no fake zeros anywhere |
| P11 | Operations + docs + e2e/visual-regression | ☐ | — | one-command run, RUNBOOK |

Status key: ☐ todo · ◐ in progress · ☑ done. Put the plan path in **Plan** once a PLAN
session writes `docs/plans/P{N}-{name}.md`.
