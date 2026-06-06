# CLAUDE.md — dz-dashboard

Read this fully. It is the only doc loaded every session, so it stays short.
Everything else is read **on demand, by section**, never wholesale.

## What this is

`dz-dashboard` (Phase 2) = a read-only analytics BFF + a presentation-only SPA over the
Phase 1 `ff-pipeline` SQLite DB.

- `src/ff_dashboard/` — Python/FastAPI. `analytics/` = pure `rows → metrics` functions
  (no FastAPI). `api/` = routes + pydantic schemas + OpenAPI. Reads the DB **read-only**
  via `ff_pipeline.repository`. Port 8800.
- `web/` — React+TS+Vite SPA. **Pure presentation, zero business logic.** Talks only to
  the BFF through a client **generated** from `/openapi.json`.

The boundary is the product. All math lives in `analytics/`, tested. The frontend cannot
disagree with the backend because the frontend does no math.

## Hard rules (never violate)

- **Never write to the DB.** No INSERT/UPDATE/DELETE; no import of Phase 1
  write/crawler/normalizer/scoring-write code. Only `ff_pipeline.repository` (+ pure
  `scoring` helpers for display). Open read-only / WAL.
- **No metric math in `web/`.** It belongs in `ff_dashboard/analytics/`.
- **Never hand-edit the generated API client** (`web/src/lib/api/`). Change the BFF
  schema and run `npm run gen:api`.
- **Never render 0 for missing data.** Use `available:false` / the `DataGap` affordance.
  Gaps that exist: an unscored current/in-progress season (the pre-2016 per-player
  reconstruction has landed — `player_stats_scored` now spans 2010–2025; F-51),
  current-season-only availability, partial DST. The unscored gap is **data-driven on the
  per-season `is_scored` flag** — never hardcode a year.
- **Don't modify Phase 1** except additive read-only helpers in
  `ff_pipeline/repository/queries.py`.
- **Don't merge milestones.** Finish one cleanly before the next.
- Commit trailers: `AI-Model` / `Prompted-By` / `Reviewed-By`. **Never** `Co-Authored-By: Claude`.
  Git model: `feature/*` → `dev` → `main`.

## Token budget — the operating discipline

This project's bottleneck is context, not capability. A session that reads every doc and
dumps every test log hits the limit mid-milestone and stalls. Default to **less in context**:

1. **Never open generated / lock / vendor files.** They are huge and add nothing:
   `web/package-lock.json`, `uv.lock`, `web/src/lib/api/schema.d.ts` and anything under
   `node_modules/`, `.venv/`, `web/dist/`, `web/playwright-report/`, `htmlcov/`.
   For the API surface, run `npm run gen:api` + the drift check — do not read the schema.
2. **Read docs by section, not whole.** Use the doc map below. Most milestones touch 1–2
   doc sections. Don't re-read a doc you read earlier in the same session.
3. **Re-establish state from `PROGRESS.md`, not by re-exploring.** It records what's done,
   what's next, and the few files that matter right now. Reading it is ~1 grep's cost vs.
   re-reading `analytics/` and `web/`.
4. **Quiet, scoped tooling.** During iteration run the *one* test file you're touching.
   Run the full gate **once**, at the end. Use quiet flags and read only failures
   (see `.claude/skills/green-gate/`). Don't paste passing output back.
5. **Split the work across threads** (see Session model). A written plan/handoff on disk is
   cheaper than carrying the whole milestone in one context window.
6. When unsure whether to read something large, **grep for the symbol first**, then open
   only the matching span with a line range.

## Doc map — read the section, not the file

`PHASE2_KICKOFF.md` is the human kickoff; you don't need to re-read it each session.

| Doc | Read it when… | Usually need |
|-----|---------------|--------------|
| `docs/00_SEAM.md` | orienting on repo boundaries / Phase 1 seam | skim |
| `docs/01_SPEC.md` | scope is unclear | a paragraph |
| `docs/02_ARCHITECTURE.md` | adding a module/route | the layout block |
| `docs/03_DATA_ACCESS.md` | touching DB reads / gaps | the gap table |
| `docs/04_ANALYTICS_MODEL.md` | writing an `analytics/` metric | that metric's § only |
| `docs/05_API_CONTRACT.md` | adding/changing an endpoint | that endpoint's shape |
| `docs/06_DESIGN_SYSTEM.md` | building primitives/tokens (P3) | tokens + the primitive |
| `docs/07_PAGES_AND_VIEWS.md` | building a page | that page's § only |
| `docs/08_TESTING_STRATEGY.md` | deciding what to test | the relevant test kind |
| `docs/09_ROADMAP.md` | every milestone — confirm scope + "Done when" | the one P# row |
| `docs/10_OPEN_QUESTIONS.md` | a decision is ambiguous | the one Q |

Use `CHANGELOG.md` for pass/PR history; keep `PROGRESS.md` for current state only.

Per-milestone deep-doc hints (from the roadmap): P3→06; P5→04 §3 + 05/07; P6→04 §4–7.

## Session model — plan / build / verify

A milestone is **not** one thread. Split it; hand off via files on disk:

- **PLAN session** — read only the doc sections for this P#, write
  `docs/plans/P{N}-{name}.md` (scope, files to touch, metric/endpoint signatures, test list,
  "Done when"), commit it. No implementation. Cheap, ends well under the limit.
- **BUILD session(s)** — read the plan + `PROGRESS.md` + only the doc sections the plan
  cites. Implement against the plan. Update `PROGRESS.md` as you go. If context gets tight,
  commit a checkpoint, write the next step into `PROGRESS.md`, and stop — resume in a fresh
  thread. A clean checkpoint beats a truncated session.
- **VERIFY session** — run the green gate, fix failures, do the manual click-through, commit
  with trailers. Keep the gate output out of context except failures.

Use the `milestone-session` and `green-gate` skills under `.claude/skills/`.

## Commands

Backend (repo root):
```
uv run pytest tests/dashboard -q        # scope to a file while iterating: ... tests/dashboard/test_power.py
uv run ruff check -q && uv run ruff format --check
uv run mypy src/ff_dashboard
```
Frontend (in `web/`):
```
npm run gen:api && git diff --exit-code web/src/lib/api   # contract drift check
npm run typecheck && npm run lint
npm run test
npm run test:e2e          # slow + noisy; VERIFY session only, redirect output to a file
```
Forbidden-import / write check:
```
git grep -nE "INSERT|UPDATE |DELETE |upsert|crawler|normalizer" src/ff_dashboard
```

## Done when (every milestone)

- The P# "Done when" in `docs/09_ROADMAP.md` is satisfied.
- Full gate green (backend pytest+ruff+mypy; frontend gen:api drift + typecheck+lint+test;
  e2e where the milestone calls for it).
- You opened the new view(s) and clicked through.
- `PROGRESS.md` updated; committed with the trailer format.
