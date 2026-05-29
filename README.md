# Phase 2 Handoff Package — Fantasy Football Analytics Dashboard

> **Status: DRAFT FOR REVIEW.** This is a complete planning package for **Phase 2: the
> dashboard** of the Danger Zone fantasy football system. It is written to the same
> standard as the Phase 1 handoff so it can be handed straight to Claude Code — but it
> bakes in several design decisions (data-access strategy, frontend stack, visual
> direction, which analytics to build first) that you should review and sign off on
> before any code is written. The decisions needing your input are collected in
> `docs/10_OPEN_QUESTIONS.md`; everything else flows from them.

Phase 2 turns the Phase 1 data foundation into a clean, fast, visually engaging web app
for exploring 16 seasons of league history and the live current season.

## What's in this package

```
phase2_handoff/
├── README.md                       ← you are here
├── PHASE2_KICKOFF.md               ← copy/paste into Claude Code to start a milestone
├── prerequisites.md                ← what YOU must do/confirm before kickoff
└── docs/
    ├── 01_SPEC.md                  ← functional & non-functional requirements
    ├── 02_ARCHITECTURE.md          ← BFF + SPA design, module boundaries, stack
    ├── 03_DATA_ACCESS.md           ← how Phase 2 reads Phase 1 data + data reliability map
    ├── 04_ANALYTICS_MODEL.md       ← every derived metric, with exact definitions
    ├── 05_API_CONTRACT.md          ← the analytics API the frontend consumes
    ├── 06_DESIGN_SYSTEM.md         ← tokens, type, color, layout, components, a11y
    ├── 07_PAGES_AND_VIEWS.md       ← screen-by-screen IA + which charts/endpoints each uses
    ├── 08_TESTING_STRATEGY.md      ← BFF, component, e2e, contract, visual-regression
    ├── 09_ROADMAP.md               ← milestone-by-milestone build order
    └── 10_OPEN_QUESTIONS.md        ← decisions for you to confirm + deferred items
```

## Read in this order

1. **`prerequisites.md`** — short. Confirms Phase 1 is in the state Phase 2 assumes.
2. **`docs/10_OPEN_QUESTIONS.md`** — read this *early*. It surfaces the handful of decisions
   the rest of the package assumes, so you can redirect before reading the detail.
3. **`docs/01`–`docs/09`** — end-to-end or skim by appetite.
4. **`PHASE2_KICKOFF.md`** — when you're ready to build.

## The one-paragraph summary

Phase 2 is **two new pieces plus a contract between them**: a small Python analytics
service (`ff_dashboard`, a backend-for-frontend) that reuses Phase 1's repository layer
to read the SQLite database directly and computes every derived metric server-side; and a
React + TypeScript single-page app that is *pure presentation* — it calls the analytics
API, renders tables and charts, and holds no business logic. Splitting it this way keeps
the heavy aggregation in tested Python (same stack, same DB, fast SQL) and keeps the
frontend thin, swappable, and easy to polish. The recommended visual direction leans into
the league's "Danger Zone" identity: a dark, HUD-inspired aesthetic with afterburner-orange
accents — distinctive, not a generic dashboard.

## Why a backend-for-frontend instead of "just call the Phase 1 API from the browser"

The single most important Phase 2 decision. Three reasons the BFF wins for this project:

- **Aggregation belongs in SQL, not the browser.** A 16-season records book, all-time
  head-to-head tables, and power rankings touch ~180k scored rows. The Phase 1 read API is
  deliberately *non-analytical* and paginated (max 500 rows/call). Doing those rollups
  client-side means dozens of round-trips and duplicated, untested logic in TypeScript.
- **Analytics is Phase 2's job by Phase 1's own charter.** `06_API_CONTRACT.md` (Phase 1)
  states the read API has "no analytical computations… Phase 2/3 compute those." The BFF is
  where those computations live.
- **It respects the repository boundary instead of breaking it.** The BFF *imports
  `ff_pipeline.repository`* (the sanctioned DB-access layer) for reads and adds a new
  `analytics/` package. No new code reaches into crawler internals; the frontend never
  touches the database. Same monorepo, same models, same migrations.

The alternative (browser-only) and the trade-offs are written up for your sign-off in
`docs/10_OPEN_QUESTIONS.md` (Q1).

## What "done" looks like for Phase 2

A single command — `dz-dashboard dev` (or `make dev`) — that brings up the analytics API
and the web app together, and a browser experience where you can:

1. Land on a **command center** showing live standings, this week's matchups, the power
   ranking, and recent league activity.
2. Drill into any **season**, **week**, **matchup box score**, **team**, **owner**, or
   **player** with clean navigation and no dead ends.
3. See **head-to-head all-time records** between any two managers (the rivalry view).
4. Browse a **records book / hall of fame** (highest score ever, biggest blowout, best and
   worst draft values, longest streaks, championship history).
5. Read every number through **charts and visualizations** — scoring trends, standings
   over time, positional breakdowns, projection-vs-actual — not just tables.
6. Do all of the above **fast** (sub-200ms warm API responses) and **offline-capable** on
   your own machine, with the same dark, characterful UI throughout.

Plus: a documented component library and design tokens so future polish is additive; a
typed client generated from the API's OpenAPI schema; test coverage on every analytics
metric; and a clear extension path for the views you'll inevitably want once you start
using it.

## Inherited from Phase 1 (confirmed, not re-litigated)

- **Data lives in one SQLite file** the BFF reads read-only. Postgres swap remains a
  `DATABASE_URL` change.
- **Python 3.11+, uv, ruff, mypy --strict, pytest, structlog** — Phase 2's backend matches.
- **Git: `feature/*` → `dev` → `main`; AI trailers on commits** (see Phase 1 `CONTRIBUTING.md`).
- **Real, reliable data**: nflverse raw stats (16 seasons), scored stats (2016–2025),
  player ID resolution, transactions, and reconstructed standings/lineups/matchups.
  **Known gaps Phase 2 must surface honestly**: 2010–2015 unscored; historical
  free-agent/waiver *availability* is current-season-only; team-defense (DST) scoring is
  incomplete. See `docs/03_DATA_ACCESS.md` for the full reliability map.
