# 09 — Roadmap

Milestone-by-milestone build order for Phase 2. As in Phase 1, each milestone is a coherent
unit of work (roughly a Claude Code session), produces something testable, and depends only
on earlier milestones. Two ordering rules are deliberate:

- **Analytics before UI for any given feature** (the BFF metric + its test land before the
  view that renders it), so the frontend always renders a tested, correct number.
- **Design system before pages** (M3 before M5+), so views are composed from durable parts.

## Milestone summary

| # | Milestone | Est. | Deliverable |
|---|-----------|------|-------------|
| P0 | Prereqs & data-readiness gate | 0.5–1 hr | Phase 1 reconstruction complete & verified; data coverage confirmed |
| P1 | BFF bootstrap | 1–2 hr | `ff_dashboard` package, settings, read-only DB reuse, `/health` + `/v1/meta` |
| P2 | Analytics core + endpoints (data-ready) | 3–4 hr | standings, owners-career, records, players, h2h — metrics + tests + endpoints |
| P3 | Frontend bootstrap + design system | 3–4 hr | Vite/React/TS app, tokens, primitives, charts, generated client, app shell |
| P4 | Home + Standings + Manager profile | 3–4 hr | first end-to-end vertical slice (data → API → screen) |
| P5 | Matchups + Box score (+ optimal lineup) | 3–4 hr | the richest view; depends on reconstruction |
| P6 | Rivalries + Records book | 2–3 hr | the league's emotional core |
| P7 | Players + Stats explorer + Team page | 3–4 hr | exploration depth |
| P8 | Draft views | 2 hr | draft board + value |
| P9 | Power ranking + standings/power timelines | 2 hr | the chart-heavy comparative views |
| P10 | Global search + coverage/about + gap polish | 2 hr | cross-cutting UX; honesty affordances everywhere |
| P11 | Operations + docs + e2e/visual-regression pass | 2–3 hr | one-command run, RUNBOOK, full test gate |

**Total:** ~30–35 hours of focused work with Claude Code; expect 2–3 weeks part-time. Heavier
than Phase 1's backend-only effort because there are two domains plus a contract seam.

---

## P0 — Prerequisites & data-readiness gate

**Goal:** confirm the data Phase 2 assumes actually exists before building views on it.

**Tasks:**
- Confirm Phase 1 `ff-pipeline reconstruct --start 2010 --end 2025` has completed and
  `verify --sweep` meets the Phase 1 bar (this was item C5 pending at handoff).
- Confirm `ff-pipeline serve` / DB path; capture `DATABASE_URL`.
- Snapshot the DB coverage: which seasons have scored rows, standings, lineups, matchups.

**Done when:** a one-paragraph data-readiness note exists; the coverage matches
`03_DATA_ACCESS.md`. If reconstruction is *not* done, P1–P4 (which lean on already-solid
data: players, stats, owner records) can still proceed; P5 waits.

## P1 — BFF bootstrap

**Goal:** the analytics service exists, reads the DB read-only, and reports coverage.

**Tasks:**
- Create `src/ff_dashboard/` per `02_ARCHITECTURE.md`; add to the same `pyproject.toml`
  (new optional deps minimal — FastAPI/uvicorn already present from Phase 1).
- `settings.py` (DB path, host/port, cache TTL); `api/main.py` app factory; `deps.py`
  reusing `ff_pipeline.repository` sessions in **read-only / WAL** mode.
- Reuse Phase 1's envelope + error handlers by importing them (`build_meta` from
  `ff_pipeline.api._meta`, `install_error_handlers` from `ff_pipeline.api.errors`) — no local
  copies, so the shapes stay identical to Phase 1.
- Implement `GET /health` and `GET /v1/meta` (coverage from `pipeline_runs` + table probes).
- `cache.py` keyed on latest `pipeline_run_id`.
- CLI/entrypoint: `dz-dashboard serve` (or a `[project.scripts]` entry).

**Done when:** `dz-dashboard serve` runs; `/health` is 200; `/v1/meta` reports real coverage;
mypy/ruff/pytest green; opening another reader while a (simulated) writer holds the file does
not error.

## P2 — Analytics core + endpoints (data-ready metrics)

**Goal:** the metrics that depend only on solid data, fully tested.

**Tasks:**
- Build the **fixture database** in `conftest.py` (see `08_TESTING_STRATEGY.md`).
- Implement + unit-test: `analytics/standings.py`, `analytics/owners.py`,
  `analytics/head_to_head.py`, `analytics/records.py` (record-only parts),
  `analytics/players.py`.
- Wire their endpoints: seasons/standings (+timeline), owners (career/seasons/trajectory/
  h2h/rivalry-matrix), records, players/stats.
- Contract tests for each endpoint; gap-behavior tests.

**Done when:** every metric has a unit test against known answers; every endpoint has a
contract test; coverage high on `analytics/`.

## P3 — Frontend bootstrap + design system

**Goal:** the SPA skeleton and the durable component layer.

**Tasks:**
- Scaffold `web/` (Vite + React + TS + Tailwind); wire QueryClient, Router, Theme provider.
- `design-system/tokens.css` (the tokens from `06_DESIGN_SYSTEM.md`); pick the two fonts
  (NOT Inter).
- Build the primitive inventory + `charts/` wrappers + `chartTheme.ts`.
- Generate the API client from `/openapi.json` (`npm run gen:api`); add the drift check.
- Build the **app shell** (top bar, season switcher, left nav, global-search placeholder,
  data-as-of indicator).
- Component tests for primitives incl. `DataGap`.

**Done when:** `npm run dev` serves the shell with working nav/season-switcher; primitives are
tested; the generated client typechecks against the live BFF schema.

## P4 — Home + Standings + Manager profile (first vertical slice)

**Goal:** prove the whole pipe end-to-end on three real pages.

**Tasks:**
- Home (composed client-side from standings/records/power — no `/v1/home` endpoint),
  Standings (+timeline chart + week-stepper), Manager profile
  (career header, trophy case, season table, trajectory chart).
- Feature tests with MSW; one e2e (land → standings).

**Done when:** the three pages render real data from the BFF; deep links work; loading/empty/
error states present; e2e green.

> **Build outcome:** Home + Standings shipped; the **Manager profile** (and Managers index)
> shipped only as `PlaceholderPage` stubs — the owner endpoints exist and are tested, but the
> views weren't composed. This is the one P4 item still outstanding (see `10_OPEN_QUESTIONS.md`
> N1).

## P5 — Matchups + Box score

**Goal:** the richest data view. **Depends on P0 reconstruction.**

**Tasks:**
- `analytics/matchups.py`: box-score enrichment, **optimal lineup / points-left-on-bench**,
  projection-vs-actual — with thorough unit tests (the optimal-lineup solver especially).
- Endpoints: week matchups, box-score.
- Views: week matchups grid (+week-stepper), box score (two-column lineups, expandable
  `StackedBreakdown` per player, totals/bench/left-on-bench `Stat`s).
- DST and pre-2016 gap handling via `DataGap`.

**Done when:** box score matches a hand-checked matchup to the decimal; gaps render honestly;
e2e (home → matchup → box score) green.

## P6 — Rivalries + Records book

**Goal:** the league's emotional core; high reuse, high delight.

**Tasks:**
- Rivalry matrix view (`Heatmap`) + pairwise page (already-built h2h endpoints).
- Records book page: superlative `Card`s with deep-links to source; championship/dynasty
  timeline; best/worst draft picks (draft records metric).
- e2e (records → click record → source matchup).

**Done when:** rivalry matrix and pairwise pages render; every record deep-links correctly.

## P7 — Players + Stats explorer + Team page

**Goal:** exploration depth.

**Tasks:**
- Player index (search/filter), player detail (scoring chart, ownership timeline,
  availability), stats explorer (top scorers, season totals), team page (roster-by-week,
  schedule, scoring trend, transactions).

**Done when:** search/filter work; player and team pages render with charts; availability gap
handled for non-current seasons.

## P8 — Draft views

**Goal:** draft board + value analysis.

**Tasks:** `analytics/draft.py` (board + pick value) + tests; draft board grid + value chart;
gap handling for seasons without captured drafts.

**Done when:** draft board renders for a covered season; steals/busts identified; gap seasons
labeled.

## P9 — Power ranking + timelines

**Goal:** the comparative, chart-heavy views.

**Tasks:** `analytics/power.py` + tests; power-ranking view + over-time `RankFlow`; integrate
into Home's "top movers." Standings-over-time already in P4; ensure both timelines share the
chart wrappers.

**Done when:** power ranking renders with its "how this is computed" explainer; timelines
animate once and read clearly.

## P10 — Global search + coverage/about + gap polish

**Goal:** cross-cutting UX and the honesty layer everywhere.

**Tasks:** `GET /v1/search` typeahead + the search UI; coverage/about page from `/v1/meta`
(incl. nflverse/Sleeper attribution); sweep every view for correct `DataGap` usage.

**Done when:** global search jumps to any entity; the coverage page is accurate; no view
renders a 0 where data is absent.

## P11 — Operations, docs, full test gate

**Goal:** the system runs itself for daily use and is documented.

**Tasks:**
- One-command up: `make dev` (BFF + Vite) for development; a documented "production-ish" local
  run (BFF via uvicorn + built static frontend served locally) for daily use.
- Decide/keep-alive story (cron `@reboot` or a user service) — mirror Phase 1 ops.
- `PHASE2_RUNBOOK.md` (start/stop, regenerate client, common breakages).
- Frontend README; update root README to describe Phase 2.
- Full e2e + visual-regression pass; CI green on both domains.

**Done when:** a fresh checkout + `uv sync` + `npm ci` + one command brings up a working
dashboard against the Phase 1 DB, with all tests green; PR `feature/* → dev`.

---

## Deliberately NOT in this roadmap

- **Phase 3** (predictions, trade/lineup advice) — separate effort; Phase 2 only *shows*.
- **Auth / multi-user / hosting** — localhost single-user; revisit only if you decide to host.
- **Real-time in-game scoring** — out of scope, matches Phase 1.
- **Writing to the DB or NFL.com** — never.
- **Mobile-native app** — the responsive web app covers mobile; native is out of scope.
