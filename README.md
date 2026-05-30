# dz-dashboard — Danger Zone Fantasy Football Analytics (Phase 2)

The Phase 2 analytics dashboard for the Danger Zone fantasy football league. It
turns the Phase 1 data foundation ([`ff-pipeline`](https://github.com/ocmooch/danger-zone))
into a fast, visually engaging web app for exploring 16 seasons of league
history and the live current season.

Phase 2 is **two pieces plus a contract between them**:

1. **`ff_dashboard`** — a read-only analytics backend-for-frontend (BFF) in
   Python/FastAPI. It reuses Phase 1's `ff_pipeline.repository` to read the
   league SQLite database and computes every derived metric server-side.
2. **`web/`** — a React + TypeScript single-page app (pure presentation). It
   talks only to the `ff_dashboard` API via a client generated from the API's
   OpenAPI schema, and holds no business logic.

> The full design package lives in `docs/` (`01_SPEC.md` … `10_OPEN_QUESTIONS.md`); see also
> `PHASE2_KICKOFF.md` in the repo root. Read `docs/02_ARCHITECTURE.md` and `docs/03_DATA_ACCESS.md` first.

## Relationship to Phase 1 (ff-pipeline)

`ff_dashboard` depends on the Phase 1 package and reads the database Phase 1
produces — **read-only, never written**:

- **Dependency:** declared in `pyproject.toml` under `[tool.uv.sources]`. The
  active source is an editable path to the sibling checkout (`../danger-zone`),
  which guarantees the ORM models match the live DB schema. A pinned git source
  is documented as the reproducible/CI alternative (see `docs/PHASE2_RUNBOOK.md`).
- **Database:** `DATABASE_URL` points at the *live* Phase 1 SQLite file (default
  `../danger-zone/data/fantasy.db`). The dashboard opens it with
  `PRAGMA query_only = ON` + WAL + `busy_timeout`, so a dashboard read can never
  write and coexists with a running pipeline.

## Quick start (backend)

```bash
uv sync --extra dev          # install ff_dashboard + ff-pipeline (editable)
uv run dz-dashboard info     # show the resolved config (no secrets — there are none)
uv run dz-dashboard serve    # serve the analytics API on http://127.0.0.1:8800
```

- `GET /health` — liveness.
- `GET /v1/meta` — data freshness + coverage (which seasons are scored, whether
  reconstruction is complete) — powers the "data as of" indicator and gap banners.
- OpenAPI at `/openapi.json`, interactive docs at `/docs`.

## Development gate

The same green-gate discipline as Phase 1; all must pass before a commit:

```bash
uv run pytest          # unit + contract tests
uv run ruff check      # lint
uv run ruff format     # format
uv run mypy src/       # strict type check
```

## Boundaries (non-negotiable)

- **Read-only.** No `INSERT/UPDATE/DELETE`; no imports of Phase 1 write/crawler code.
- **All derived-metric math lives in `ff_dashboard/analytics/`** — never in the frontend.
- **Honest about gaps.** Unscored 2010–2015, current-season-only availability, and
  incomplete DST scoring are surfaced via `available:false`, never faked as zeros.

## Status

Phase 2 is built milestone-by-milestone per `09_ROADMAP.md`. See the git log.
