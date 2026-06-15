# 08 — Testing Strategy

Phase 2 has two test domains — the Python analytics BFF and the TypeScript frontend — plus a
contract seam between them. The discipline mirrors Phase 1: pure logic is unit-tested
exhaustively; the API is contract-tested; a thin layer of end-to-end tests guards the
critical journeys. The bar for merge is the same green-gate Phase 1 uses.

## Test pyramid

```
                 ┌───────────────────────────────────┐
                 │   E2E (Playwright) — a few         │
                 ├───────────────────────────────────┤
                 │   Contract + integration (~25)     │
                 ├───────────────────────────────────┤
                 │   Unit: analytics + components (most)│
                 └───────────────────────────────────┘
```

## Backend (`ff_dashboard`) tests

Tooling matches Phase 1: `pytest`, `pytest-cov`, FastAPI `TestClient`, ruff, mypy --strict.

### The fixture database (the foundation)

Build one small, hand-authored SQLite fixture used by all analytics and contract tests. It is
the analytics equivalent of Phase 1's scoring fixtures. It must encode **known answers**:

- ≥3 seasons, ≥4 managers, with at least one manager spanning all seasons and one who joined
  late (tests owner persistence + rivalry overlap logic).
- A known champion and final standings per season (tests standings/records).
- A hand-computed **blowout**, a hand-computed **narrow win**, and a known **highest team
  score** (tests the records book to the decimal).
- A known **steal** and **bust** draft pick (tests draft value).
- Scored **DST starters** (DST is scored end-to-end) plus at least one **data-gap case**: an
  unscored 2015 season, a DEF starter slot whose row is genuinely missing, and a non-current
  season for availability — so "honest about gaps" is *tested*, not assumed.

Generate it programmatically in `conftest.py` (insert rows via the reused
`ff_pipeline.repository` models) so it stays in sync with the schema.

### Unit tests — one per analytics metric

Tests live **flat in `tests/`**, grouped by roadmap milestone rather than a nested
`unit/`-`integration/` tree — `tests/test_p<N>_<area>_unit.py` for analytics and
`tests/test_p<N>_endpoints.py` for the API (e.g. `test_p2_analytics_unit.py`,
`test_p5_matchups_unit.py`, `test_p2_endpoints.py`). The fixture DB is built once in
`tests/conftest.py`. Each analytics module is covered by a unit file:

- **Standings:** record, PF/PA, rank tiebreak, through-week, streaks.
- **Power ranking:** z-score math on a tiny known set; weight application; timeline.
- **Matchups:** bench points; **optimal lineup / points-left-on-bench** (the trickiest — test
  the slot-assignment against a hand-solved roster); projection-vs-actual.
- **Head-to-head:** pairwise tally with no double-counting (the two-rows-per-game trap);
  rivalry matrix symmetry/complementarity; closest-rivalry selection.
- **Records:** every superlative returns the right value *and* the right context row.
- **Owners:** career aggregate incl. championships/finishes; consistency stdev.
- **Draft:** pick-value definition; steal/bust identification.
- **Gap behavior:** every metric, when pointed at gap data, returns `available:false` (never
  0). This is a first-class assertion class.

Target: high coverage on `analytics/` (treat it like Phase 1 treated the scoring engine —
this is where correctness lives).

### Contract / integration tests — one per endpoint

`tests/test_p<N>_endpoints.py`, using `create_app(engine=fixture_engine)` (same pattern Phase 1
uses to bind a temp engine):

- Every endpoint in `05_API_CONTRACT.md`: 200 happy-path with the documented envelope shape;
  `400`/`404` where applicable; `503` when pointed at an empty database.
- The `meta` envelope is present and carries a `pipeline_run_id`.
- Gap endpoints return `available:false` payloads with a `reason`.
- A response-shape snapshot per endpoint guards accidental contract drift.

### Cache tests

- A rollup computed twice returns the same object and the second call doesn't re-query
  (assert via a query counter or a spy).
- A new `pipeline_run_id` invalidates the cache (different key → recompute).

## Contract seam — generated client

- The frontend's API types are generated from the BFF `/openapi.json` via
  `openapi-typescript` (`npm run gen:api` → `web/src/lib/api/schema.d.ts`).
- CI boots the real BFF and runs `npm run gen:api:check`, which diffs the live schema against
  the committed client; any drift fails the build. This makes contract drift impossible to
  merge.

## Frontend (`web/`) tests

Tooling: **Vitest** + **React Testing Library** for unit/component; **Playwright** for e2e;
**MSW** (Mock Service Worker) to stub the API with fixture responses.

### Component tests

- Each design-system primitive: renders states (default/hover/loading/empty/error), is
  keyboard-accessible, and exposes correct ARIA.
- **`DataGap`** specifically: given an `available:false` payload, the component renders the gap
  affordance and **never a 0** — the UI-side guarantee of N2.2.
- Numeric formatting (`format.ts`): records render `W-L-T`, scores keep two decimals, tabular
  alignment classes applied.

### Feature/page tests

- For each page, render with MSW-mocked endpoint responses (reuse the backend fixture's known
  answers as JSON) and assert the right numbers/labels appear and deep links resolve.
- Loading → data → error transitions render the right states.

### Visual regression (lightweight)

- Playwright screenshot snapshots of the key pages in the default dark theme to catch
  unintended layout/style drift. Keep the set small (home, standings, box score, rivalry
  matrix, manager profile) so it's maintainable.

### End-to-end (a handful)

Run against a real BFF bound to the fixture database:

1. Land on Home → see standings + matchups.
2. Home → click a matchup → box score shows per-player breakdown + points-left-on-bench.
3. Manager profile → open a rivalry → pairwise record renders.
4. Records book → click a record → deep-links to the source matchup.
5. Hit a gap (open a 2015 box score) → `DataGap` shown, no fake zeros.

## What's NOT tested (to stay sane)

- The live Phase 1 pipeline or third-party sources — Phase 2 never calls them.
- Exhaustive cross-browser; target the user's actual browser plus one fallback.
- Performance as an assertion (it's an operational target, N1); spot-check manually.

## Continuous integration

Two workflows split by cost. `ci.yml` runs the **always-on, required** backend + frontend
jobs on every push/PR to `dev`/`main`. `e2e.yml` runs the heavy contract-seam + e2e job, but
**only when code that can change its outcome changes** (`web/**`, `src/ff_dashboard/**`,
`scripts/serve_e2e.py`, `pyproject.toml`, `uv.lock`, or the workflow itself) — docs-only and
memory changes skip it. e2e is not a required check, so a path-skip can't deadlock a PR.

```
ci.yml  backend:  uv sync --extra dev → ruff check → ruff format --check → mypy src/ → pytest
        frontend: npm ci → npm run test → npm run build  (build = tsc --noEmit && vite build, the type gate)
e2e.yml e2e:      uv sync + npm ci → boot BFF → npm run gen:api:check  (contract drift)
                           → playwright install chromium → playwright test   [path-scoped]
```

Notes on the as-built workflows:
- The backend + e2e jobs check out the sibling `ff-pipeline` (Phase 1) as `../danger-zone` via
  a deploy key, because `[tool.uv.sources]` points at the editable path (swap to the pinned git
  tag to drop that step — see `PHASE2_RUNBOOK.md`).
- There is **no `npm run lint`** target; linting on the frontend is `tsc` (typecheck). Ruff is
  the backend linter.
- **Visual-regression** (`e2e/visual.spec.ts`) is now in the CI gate with committed
  Chromium/Linux baselines. Refresh them with `make e2e-update` after intentional UI changes.
