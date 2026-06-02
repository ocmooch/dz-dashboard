# 10 — Open Questions & Default Decisions

Originally the pre-build sign-off sheet. Phase 2 is now built (P0–P11), so this doc has been
re-cut into **what was decided (resolved as built)**, **what is still genuinely open
(deferred)**, **new issues the build surfaced**, and **locked-in** choices. Each item still
links to the doc that depends on it.

---

## Resolved — decided and built

The seven sign-off questions are all settled by the as-built system. Recorded here so the
rationale isn't lost; none needs further action unless you want to revisit.

| # | Question | Decision (as built) |
|---|----------|---------------------|
| Q1 | Data-access architecture | **BFF** reusing `ff_pipeline.repository`, read-only/WAL; all analytics server-side; SPA is pure presentation. (docs 02/03/05) |
| Q2 | Frontend stack | React 18 + TypeScript + Vite + Tailwind + TanStack Query + React Router + Recharts + `openapi-typescript`/`openapi-fetch`. Primitives hand-built (no shadcn). |
| Q3 | Visual direction | **"Danger Zone" HUD** — dark instrument-panel, afterburner-orange accent (`#ff6a1a`), mono/tabular numerics. Fonts: **Saira Condensed** (display), **IBM Plex Sans** (body), **IBM Plex Mono** (numbers) — not Inter. A light token set exists but is not exposed as a toggle (see Q10). |
| Q4 | View priority | Built per default order; the Manager index/profile pages are now built (`feature/managers-page`). Only the Playoffs/Bracket view remains unbuilt — see "New issues" below. |
| Q5 | Standings tiebreaker | Prefer reconstructed `teams.final_rank`; else compute wins→points-for, exposing `rank_basis` + `tiebreak_caveat` (computed & pre-2019). Old best-of-3 not re-derived. (`04_ANALYTICS_MODEL.md` §1) |
| Q6 | Power-ranking model | Z-score blend **0.5·PPG + 0.3·win% + 0.2·last-3-PPG**; weights in one constant and shipped in the payload's `weights`. (`analytics/power.py`) |
| Q7 | Optimal-lineup definition | Implemented in `analytics/matchups.py` (optimal-lineup / points-left-on-bench) reading the roster slot configuration; covered by a hand-solved unit test. |

---

## Deferred to implementation

These shipped at their defaults and remain reversible — listed with their as-built status.

### Q8. Keep-alive / run model for daily use

`make dev` for development is clear. For daily use, do you want the BFF + built frontend
launched on login (cron `@reboot` / a user service, mirroring Phase 1's cookie-era ops), or
are you fine running one command when you want it? **Default:** one command now; document the
auto-start option.

**As built:** one-command (`make serve`). Both auto-start options are provided and documented
— `scripts/dz-dashboard.service` (systemd user service, preferred) and `scripts/cron.example`
(`@reboot`). Nothing is installed by default. *(Settled at default.)*

### Q9. Caching aggressiveness

**Default:** in-process memoization keyed on `pipeline_run_id`. If the heaviest rollups
(rivalry matrix, records over 16 seasons) feel slow on first hit, we can precompute them into
a small materialized cache table on pipeline completion. **Default:** in-process only; revisit
if first-hit latency is noticeable.

**As built:** in-process only (`cache.py`, `AnalyticsCache`, keyed on
`latest_pipeline_run_id`). No materialized table. *(Open only if first-hit latency bites.)*

### Q10. Theme toggle

**Default:** dark-first, with a light theme implemented behind the token system but not
necessarily exposed in the UI initially. Want a visible light/dark toggle on day one?

**As built:** dark-first; light token set exists in `tokens.css` (`[data-theme="light"]`) but
**no toggle is wired** in the UI. **Still open** if you want a visible switch.

### Q11. Avatars / team logos / manager photos

Sleeper-style chips look best with avatars. Phase 1 may not store these. **Default:**
initials/monogram chips generated from names; optional later enhancement to let you drop in
manager avatars via a small local config. Confirm if you want avatars early.

**As built:** monogram chips from names; no avatar config. **Still open** as an enhancement.

### Q12. Mobile priority

**Default:** laptop-first, responsive down to phone (usable, not pixel-perfect). If you'll
mostly check it on a phone, we raise mobile to a first-class target and adjust layouts/charts
accordingly. **As built:** laptop-first responsive, per default.

### Q13. Exports / sharing

**Default:** none in Phase 2 (it's localhost, single-user). A "copy chart as image" or "export
table as CSV" affordance is a cheap later add if you want to share records in the league chat.
**As built:** none. **Still open** as a later add.

---

## New issues (surfaced by the build — need a decision)

These are gaps between the design package and the as-built system, found in the documentation
drift pass. Each is a real "still needs address," not a question of taste.

### N1. Manager index + Manager profile pages — RESOLVED

Both `/managers` (career leaderboard: league-legends strip + sortable career table) and
`/managers/{owner_id}` (dossier: career header, trophy case, `RankFlow` trajectory, season
table, rivalry snapshot) were composed on `feature/managers-page` against the already-built,
tested `/v1/owners/*` endpoints. Win % is derived client-side; record-only seasons render a
`DataGap` for points-for rather than a fake 0. Nav item marked ready; feature tests added.

### N2. Playoffs / Bracket view never built

`F2.3` called for a playoff bracket / final-results view; neither the `/bracket` route nor the
`GET /v1/seasons/{id}/bracket` endpoint exists. Champion / runner-up / last-place are available
today via the season summary and records book. **Decision needed:** build the bracket view
(with the "post-regular-season weeks, not a proven bracket" caveat) or accept the season-summary
coverage as sufficient and close `F2.3`.

### N3. `/v1/home` composite was dropped in favor of client-side composition *(resolved — recorded)*

The home view composes `/v1/seasons/{id}/standings` + `/v1/records` + `/v1/seasons/{id}/power`
on the client rather than via a single `/v1/home` endpoint + `analytics/league.py`. The SPA
still does no math (orchestration only). Docs 02/04/05/07 have been updated to match. No action
unless first-paint round-trips become a concern (then re-introduce a composite).

### N4. Visual-regression baselines not committed → not in the CI gate

`e2e/visual.spec.ts` exists but per-platform snapshots aren't committed, so CI runs only
`playwright test journeys`. Generate baselines on a browser-capable host (`make e2e-update`),
commit them, and add `playwright test visual` to the `e2e` job to close the gate.

---

## Locked-in (inherited from Phase 1; not re-litigated)

- **SQLite as the data source**, read-only, with the documented Postgres path.
- **Python 3.11+, uv, ruff, mypy --strict, pytest, structlog** for the backend; same
  green-gate-before-merge discipline.
- **Same git model** (`feature/*` → `dev` → `main`) and **AI commit trailers**
  (`AI-Model` / `Prompted-By` / `Reviewed-By`; never `Co-Authored-By: Claude`).
- **No writes, no predictions, no pipeline control from the UI, localhost-only.**
- **Honesty about data gaps is non-negotiable** — unscored 2010–2015, current-season-only
  availability, and any genuinely-missing scored row (including a DST team/week) are surfaced,
  never faked. DST is now scored end-to-end.

---

## Questions to revisit at the end of Phase 2 (before Phase 3)

- Which views did you actually use? Which planned ones went untouched?
- Did any analytics metric need a definition change once you saw it on real data?
- Is the in-process cache adequate, or do the big rollups want precomputation?
- Did the BFF stay a thin analytics layer, or is it creeping toward logic Phase 3 should own?
- What new views did you wish for while using it (the most valuable input for Phase 3 scope)?
