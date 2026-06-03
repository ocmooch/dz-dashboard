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

- Branch: `feature/player-last-year-played` (cut from `dev`; Phase A merged via PR #24)
- Last work: **Players-view audit — Phase B (B1 + B2)**. The pinned ff-pipeline regen
  landed three new `PlayerOut` fields (`last_season` = D1, `first/last_rostered_season`
  = D4 option b), so B1/B2 are unblocked. Frontend-only change.
- Gate status: frontend green (typecheck, contract drift clean vs live BFF, 128 vitest).
  Backend untouched. Verified against the real DB: 38/40 sampled league players have
  `last_season` populated; NULLs render the gap affordance.

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

- **This session's mode:** VERIFY (done) → ready to PR `feature/player-last-year-played` → `dev`.
- **Phase B remaining (still gated):** B4 confirm the contamination guard no longer fires
  (D5). B1–B3 are done. See Phase B in `docs/plans/players-audit-dashboard.md`.

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
