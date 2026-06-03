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

- Branch: `feature/players-audit` (cut from `dev`)
- Last work: **Players-view audit — Phase A** (dashboard-only fixes from
  `docs/plans/players-audit-dashboard.md`). DB-side fixes handed off in
  `docs/handoffs/players-audit-danger-zone.md` (Phase 1 work underway).
- Gate status: backend green (156 pytest, ruff, mypy, write-safety); frontend green
  (typecheck, 127 vitest, contract regenerated). Click-through done on the real DB.

## What Phase A shipped

- **Index scoped to league relevance** (`scope=league` default = players ever on a
  `team_rosters` row; `scope=all` opts into the full nflverse universe). Real DB: default
  drops the ~1849 never-rostered players (incl. ghosts like A.J. Feeley) that made the
  index untrustworthy.
- **Enriched index rows**: rostered-season span + `has_scored` marker, computed in
  `analytics/players.py:list_player_index` (no SPA math).
- **Honest status on detail**: header leads with "rostered YYYY–YYYY" (from ownership);
  the unreliable nflverse `is_active` flag demoted to a muted "NFL status (nflverse)" line.
- **Ownership collapsed into spans** (`ownership_timeline`) — a busy player's 231 weekly
  rows → 22 spans; genuine mid-season trades stay legible.
- **Bio gap affordance**: missing rookie year / birth date render `DataGap`
  (`player_bio_unavailable`), never a bare dash/0.

## Next

- **This session's mode:** VERIFY (done) → ready to PR `feature/players-audit` → `dev`.
- **Phase B (gated on the danger-zone handoff):** surface "Last year played"
  (`last_season` + `PlayerOut.last_season`), restore a trustworthy active/retired signal
  once `is_active` semantics are fixed, fold relevance onto a DB helper, drop the
  contamination-guard noise. See Phase B in `docs/plans/players-audit-dashboard.md`.

## Files that matter now

- `src/ff_dashboard/analytics/players.py` — `list_player_index`, `ownership_timeline` (spans)
- `src/ff_dashboard/api/routes/players.py` — `scope` param, enriched index
- `src/ff_dashboard/api/schemas.py` — `PlayerIndexRow`, `OwnershipSpan`
- `web/src/features/players/PlayersPage.tsx` / `PlayerDetailPage.tsx`
- `docs/plans/players-audit-dashboard.md` · `docs/handoffs/players-audit-danger-zone.md`

## Open items / deviations

- League relevance = **ever-rostered only** (not "ever scored"): the pipeline scores the
  whole NFL, so "scored" is not a league-relevance signal. Documented in the plan/handoff.
- Phase A keeps all the new index reads dashboard-side (direct `select()` in analytics, the
  established pattern) rather than adding a `queries.py` helper, to avoid churn in
  danger-zone while its Phase 1 fix is in flight. Phase B (B3) can fold onto a DB helper.

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
