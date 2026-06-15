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

> The full design package lives in `docs/` (`00_SEAM.md` … `10_OPEN_QUESTIONS.md`), with the
> design handoff at `docs/DESIGN_HANDOFF.md`. Read `docs/00_SEAM.md`,
> `docs/02_ARCHITECTURE.md`, and `docs/03_DATA_ACCESS.md` first. The pre-build kickoff and
> prerequisites briefs are archived under `docs/archive/` for provenance.

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

## Run it (one command)

From a fresh checkout, `make install` once, then:

```bash
make dev      # development: BFF (:8800, reload) + Vite dev server (:5173); Ctrl-C stops both
make serve    # daily use: builds the SPA and runs ONE uvicorn serving API + SPA on :8800
```

- `make dev` → open **http://127.0.0.1:5173** (Vite proxies `/v1`, `/health`,
  `/openapi.json` to the BFF, so the browser talks to one origin).
- `make serve` → open **http://127.0.0.1:8800** (the BFF serves the built SPA
  single-origin — no second server, no CORS).
- `make help` lists every target. For always-on (logout/reboot) use the systemd
  user service in `scripts/dz-dashboard.service` (cron `@reboot` alternative in
  `scripts/cron.example`).

The full operational playbook — start/stop, regenerating the typed client, and
common breakages — is in **[`docs/PHASE2_RUNBOOK.md`](docs/PHASE2_RUNBOOK.md)**.
Frontend detail lives in [`web/README.md`](web/README.md).

### Running by hand (no make)

```bash
uv run dz-dashboard serve --reload   # terminal 1: API on :8800
cd web && npm install && npm run dev  # terminal 2: SPA on :5173
```

## Development gate

The same green-gate discipline as Phase 1; all must pass before a commit:

```bash
make check             # runs the whole gate, both domains:
                       #   backend : pytest · ruff check · mypy src/
                       #   frontend: typecheck · vitest
```

End-to-end + visual-regression run separately (they boot a real BFF on the
fixture DB and a headless browser):

```bash
make test-e2e          # Playwright journeys + visual regression
make e2e-update        # refresh visual-regression baselines after an intended UI change
```

> First-time e2e needs the browser: `cd web && npx playwright install --with-deps chromium`.

## Boundaries (non-negotiable)

- **Read-only.** No `INSERT/UPDATE/DELETE`; no imports of Phase 1 write/crawler code.
- **All derived-metric math lives in `ff_dashboard/analytics/`** — never in the frontend.
- **Honest about gaps.** An unscored current/in-progress season (data-driven on `is_scored`),
  current-season-only availability, and any genuinely-missing scored row (including a DST
  team/week) are surfaced via `available:false`, never faked as zeros. Per-player fantasy scoring
  now spans 2010–2025 since F-51; DST itself is now scored end-to-end.

## Status

Phase 2 is built end-to-end per `09_ROADMAP.md` (P0–P12): the analytics BFF, the
full SPA (home, standings, power, matchups/box-score, rivalries, records,
players, stats, draft, coverage, global search, league history, commissioner
history, playoffs brackets, injury reports), one-command operations, and a
both-domain test gate (analytics unit + contract, component/feature, and
Playwright e2e/visual-regression). See `CHANGELOG.md` for per-pass history. The
only open dashboard branch is `feature/rivalries-insights`; remaining backlog is
upstream/data work tracked in `docs/ACTIVE_WORK.md`.
