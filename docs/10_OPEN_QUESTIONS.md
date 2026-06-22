# 10 — Open Questions & Default Decisions

Originally the pre-build sign-off sheet. Phase 2 is now built (P0–P12), so this doc has been
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
| Q3 | Visual direction | **"Danger Zone" HUD** — dark instrument-panel, afterburner-orange accent (`#ff6a1a`), mono/tabular numerics. Fonts: **Saira Condensed** (display), **IBM Plex Sans** (body), **IBM Plex Mono** (numbers) — not Inter. A future light token set is possible but not implemented (see Q10). |
| Q4 | View priority | Built per default order, including Manager index/profile and the caveated Playoffs/Bracket view. |
| Q5 | Standings tiebreaker | Prefer reconstructed `teams.final_rank`; else compute wins→points-for, exposing `rank_basis` + `tiebreak_caveat` (computed & pre-2019). Old best-of-3 not re-derived. (`04_ANALYTICS_MODEL.md` §1) |
| Q6 | Power-ranking model | Within-season z-score blend **0.40·PF/g + 0.25·all-play% + 0.20·win% + 0.15·last-3-PF/g**; weights in one constant and shipped in the payload's `weights`. A points-dominant lens (its terms correlate with scoring), not a forecast. Surfaced as the Standings `?lens=power` toggle + a Playoffs entry snapshot, not a top-level space. (`analytics/power.py`) |
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

**As built:** dark-only. `tokens.css` is structured so a light token set can be added later, but
there is **no `[data-theme="light"]` token set and no UI toggle** today. **Settled 2026-06-08:
keep dark-only** — the HUD aesthetic is deliberately dark. `tokens.css` stays structured for a
light set if ever wanted, so this remains reversible.

### Q11. Avatars / team logos / manager photos

Sleeper-style chips look best with avatars. Phase 1 may not store these. **Default:**
initials/monogram chips generated from names; optional later enhancement to let you drop in
manager avatars via a small local config. Confirm if you want avatars early.

**As built:** monogram chips from names. **Decided 2026-06-08: pull team logos from the DB
when present, monogram fallback.** Phase 1's regen populated `teams.team_avatar_asset_id` (190
rows) with bytes in the content-addressed asset store; the BFF streams them via
`GET /v1/teams/{team_id}/avatar` and the `Chip` renders the logo, falling back to the monogram on
any null/404/load-error. **Owner/manager photos stay a true source gap** — `owner_avatar_asset_id`
is populated on 0 rows, so manager chips remain monograms pending an upstream backfill (relate F-06).

### Q12. Mobile priority

**Default:** laptop-first, responsive down to phone (usable, not pixel-perfect). If you'll
mostly check it on a phone, we raise mobile to a first-class target and adjust layouts/charts
accordingly. **As built:** laptop-first responsive, per default. **Settled 2026-06-08: keep
laptop-first** — no phone-first rework. Reversible if usage moves to mobile.

### Q13. Exports / sharing

**Default:** none in Phase 2 (it's localhost, single-user). A "copy chart as image" or "export
table as CSV" affordance is a cheap later add if you want to share records in the league chat.
**As built:** none. **Settled 2026-06-08: no exports** — localhost single-user. Reversible; revisit
only if league-chat sharing becomes a real need.

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

### N2. Playoffs / Bracket view — SHIPPED & MERGED (PRs #55, #60)

`F2.3` began as a caveated `/bracket` route backed by `GET /v1/seasons/{id}/bracket` (proven
post-regular-season rows only, `available:false` when none exist). It has since shipped as a
**true bracket visualization** (PR #55) and then **split into separate championship and
consolation brackets** (PR #60), all merged to `dev` and promoted to `main`. The view still does
not invent advancement it cannot prove. **F-49 remains upstream** for source-derived
consolation/playoff-berth metadata — until it lands, `made_playoffs` stays `None` where a bracket
can't be inferred honestly.

### N3. `/v1/home` composite was dropped in favor of client-side composition *(resolved — recorded)*

The home view composes `/v1/seasons/{id}/standings` + `/v1/records` + `/v1/seasons/{id}/power`
on the client rather than via a single `/v1/home` endpoint + `analytics/league.py`. The SPA
still does no math (orchestration only). Docs 02/04/05/07 have been updated to match. No action
unless first-paint round-trips become a concern (then re-introduce a composite).

### N4. Visual-regression baselines — RESOLVED

`e2e/visual.spec.ts` now has committed Chromium/Linux baselines, and CI runs the full Playwright
suite (`npx playwright test`) rather than journeys only. P11's original visual-regression gate is
closed for the supported CI platform.

### N5. Upstream data work is partially retired, not fully closed

The dashboard fix-passes are merged. **Closed since:** F-54 (season-correct player NFL team, PR #51);
the **Data Integrity & Coverage program** (cross-source identity links + identity-aware ingest +
`/v1/meta/coverage` — dashboard #77, upstream crosswalk); and **FAAB capture** (2021–2025
`extra_data.faab_bid` landed upstream and is surfaced as bid pills + a weekly remaining-budget view,
#90–#93). Several UP items remain outside this repo: ownership-succession history (F-06, ⊘ blocked on
a source), residual player-identity metadata cleanup (F-25 D1/D2/D3/D4), pre-2016 reconstructed-
scoring validation (F-27), playoff/consolation metadata (F-49), and consuming the **exact**
transaction dates/types as a richer tier beyond the derived roster-diff log (F-37 remainder).

New-session note: these are primarily `../danger-zone` tasks. For F-25, start from
`docs/handoffs/players-audit-danger-zone.md` but use the status-update counts, not the original
counts. For F-27, sanity-check reconstructed 2010-2015 scores against source NFL.com/team totals
before calling them final. For F-49, prefer fixing source flags over adding dashboard inference.

### N6. Conferences feature was silently dead at runtime — RESOLVED (PR #82)

The conferences feature was dead at runtime: `analytics/conferences.py` imported `SeasonConference`
and read `Team.conference_id`, neither of which the Phase-1 ORM maps, so its guard set
`_CONFERENCE_MODELS_AVAILABLE = False` and the 2010–2019 conference era was invisible. **The
proposed raw-SQL repair turned out to be moot — the presumed conference tables/columns do not exist
in the live Phase 1 schema at all.** Resolved instead by `feature/bff-weekly-division-standings`
(PR #82): the dashboard now owns a reviewed NFL.com 2010–2019 division artifact, returns **exact
weekly historical division standings** (records + source ranks) mapped through `teams.team_abbrev`,
and renders complete historical division tables on Standings with an honest mapping gap on mismatch.
2020+ remains explicitly ungrouped. (See `docs/ACTIVE_WORK.md` §1/§6.1.)

---

## Locked-in (inherited from Phase 1; not re-litigated)

- **SQLite as the data source**, read-only, with the documented Postgres path.
- **Python 3.11+, uv, ruff, mypy --strict, pytest, structlog** for the backend; same
  green-gate-before-merge discipline.
- **Same git model** (`feature/*` → `dev` → `main`) and **AI commit trailers**
  (`AI-Model` / `Prompted-By` / `Reviewed-By`; never `Co-Authored-By: Claude`).
- **No writes, no predictions, no pipeline control from the UI, localhost-only.**
- **Honesty about data gaps is non-negotiable** — an unscored current/in-progress season
  (data-driven on `is_scored`), current-season-only availability, and any genuinely-missing
  scored row (including a DST team/week) are surfaced, never faked. Per-player fantasy scoring now
  spans 2010–2025 since F-51, and DST is now scored end-to-end.

---

## Questions to revisit at the end of Phase 2 (before Phase 3)

- Which views did you actually use? Which planned ones went untouched?
- Did any analytics metric need a definition change once you saw it on real data?
- Is the in-process cache adequate, or do the big rollups want precomputation?
- Did the BFF stay a thin analytics layer, or is it creeping toward logic Phase 3 should own?
- What new views did you wish for while using it (the most valuable input for Phase 3 scope)?
