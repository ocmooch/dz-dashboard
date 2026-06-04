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

- **Active: fix-pass P1 (review-fixes program) — VERIFY complete on branch
  `feature/fix-P1-analytics`; PR to `dev` open.** Backend-only analytics correctness/scoping/enrichment for
  findings F-32, F-22, F-31, F-10, F-12, F-23, F-17, F-13. Plan: `docs/plans/fix-P1-analytics.md`;
  tracker: `docs/plans/REVIEW_FIXES_ROADMAP.md`. What shipped this build:
  - **F-32** new `analytics/season_schedule.py` (config-driven `SeasonSchedule` + `phase_of_week`
    / `fantasy_week_range`); `_CONFIRMED` empty pending the 1-13→1-14 switch year (roadmap input #1)
    so behaviour is unchanged today.
  - **F-22** records era split in `records.py`: team/score/margin records over `team_record_window`
    (all team-totals seasons, 2010–2025), player records over `scored_window` (2016–2025); payload
    adds `team_record_era`.
  - **F-31** new `analytics/stats.py:season_totals` week-capped to `championship_week`; route
    `players.py` imports it instead of the Phase-1 query (shape unchanged → no drift).
  - **F-10** `owners.py:owner_seasons` adds derived `result` + data-derived `made_playoffs`.
    VERIFY found the real DB leaves `is_consolation` unpopulated and flags every post-season game
    `is_playoff`, so `made_playoffs` returns `None` unless a season's bracket is a proper subset of
    the league (honest gap, never fabricated). Root cause is upstream → new finding **F-49** (UP).
  - **F-12/F-23** `head_to_head.py:pairwise_record` adds `cumulative_margin_for_a` + `closest_meeting`.
  - **F-13/F-17** `matchups.py:week_matchups` adds `is_close`/`is_blowout` (backend constants) +
    per-side `entering_record`.
  - Schemas updated + `npm run gen:api` regenerated (drift captured in `web/src/lib/api/schema.d.ts`).
  - **Full gate green:** backend **182 passed** (156 + 26 fix-P1 tests), ruff clean, mypy clean,
    write-safety clean; frontend **gen:api no drift**, typecheck clean, **vitest 128 passed** (`lint`
    is N/A — no script/eslint config in `web/`). e2e skipped (backend-only pass; new fields render in P5).
  - **Real-DB click-through (VERIFY):** F-22 confirmed (a 2011 game holds `lowest_team_score` 36.8);
    F-12/F-23 (`cumulative_margin_for_a`, `closest_meeting`), F-13/F-17 (`is_close`/`is_blowout`,
    `entering_record`), F-31, F-10 `result` all serve correctly on the live BFF over the real DB.
- Branch baseline: `dev` (all P0–P11 + the players audit merged). Latest merge: PR #29 (review docs).
- **Phase 2 is functionally complete.** Every roadmap milestone has shipped artifacts on
  disk (all 11 analytics modules + routes, all web features, P11 ops: `Makefile`, `README.md`,
  `web/README.md`, `docs/PHASE2_RUNBOOK.md`, e2e `journeys`/`visual` specs). The milestone
  tracker below is updated to reflect this.
- Last substantive work: the **players-view data-honesty audit** (Phase A + B, off-roadmap),
  merged via PRs #24–26. See the Phase A/B sections below.
- Gate status: backend **156 passed**, mypy clean, write-safety clean (the lone `git grep`
  hit is a docstring in `engine.py` describing read-only enforcement, not real write code);
  frontend typecheck clean, **128 vitest**. Contract-drift check requires a running BFF.
- **Next high-value step: manual in-browser click-through** against the real DB to surface
  data/UX gaps, then triage each as backend-data vs. frontend-presentation (the split that
  worked for the players audit).

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

## What Phase B shipped (this session)

- **B1 — "Last year played"**: detail bio card now renders `PlayerOut.last_season` next to
  "Rookie year" (the nflverse NFL-career bookends); NULL → `player_bio_unavailable` gap, never 0.
- **B2 — active/retired signal**: D3 (is_active semantics) did **not** land in the regen, so
  restoring an `is_active` badge would reintroduce the audited bug. Per the handoff's own
  resolution (D4 option b), the trustworthy signal is the rostered span — already the
  header's primary status. Dropped the last assertion off the unreliable flag: removed the
  muted "NFL status (nflverse): active/retired" line entirely. `is_active` is no longer
  surfaced in the UI.
- **B3 — fold rostered span onto the DB columns (D4 option b landed)**: the pipeline now
  materializes `Player.first_rostered_season`/`last_rostered_season` (verified equal to the
  `team_rosters` MIN/MAX for all 1244 ever-rostered players, 0 mismatches). `list_player_index`
  now scopes on `last_rostered_season IS NOT NULL` and reads the span straight off the
  columns — dropping the EXISTS subquery and the GROUP BY join. The detail header reads the
  span from `PlayerOut` directly, removing the extra ownership round-trip. The fixture DB now
  backfills these columns from `team_rosters` so it honors the same invariant. Output shape
  unchanged (contract drift clean).

## Next

- **Phase B complete.** B1–B3 shipped via PR #25 (merged to `dev`). B4 confirmed this
  session — see below. No Phase B work remaining.

- **B4 — contamination guard confirmed (D5 landed):** verified against the real DB
  (`../danger-zone/data/fantasy.db`, read-only). The handoff's D5 audit query returns 0
  duplicate cross-team roster groups (now enforced by `uq_team_rosters_season_week_player`).
  Replicating `matchups.py:409`'s home∩away intersection across all 3002 two-sided matchups
  found 0 firing. Guard kept as defense-in-depth; no code change. See Phase B in
  `docs/plans/players-audit-dashboard.md`.

## Files that matter now

- `src/ff_dashboard/analytics/players.py` — `list_player_index`, `ownership_timeline` (spans)
- `src/ff_dashboard/api/routes/players.py` — `scope` param, enriched index
- `src/ff_dashboard/api/schemas.py` — `PlayerIndexRow`, `OwnershipSpan`
- `web/src/features/players/PlayersPage.tsx` / `PlayerDetailPage.tsx`
- `docs/plans/players-audit-dashboard.md` · `docs/handoffs/players-audit-danger-zone.md`

## Open items / deviations

- League relevance = **ever-rostered only** (not "ever scored"): the pipeline scores the
  whole NFL, so "scored" is not a league-relevance signal. Documented in the plan/handoff.
- ~~Phase A keeps index reads dashboard-side rather than a `queries.py` helper.~~ **B3 done:**
  D4 option (b) landed `Player.first/last_rostered_season` columns; `list_player_index` and the
  detail header now read those columns directly instead of joining `team_rosters`.

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
