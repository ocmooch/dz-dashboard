# Phase 2 Runbook

Operational playbook for the day-2 life of the **dz-dashboard** (Phase 2). Read this when
you want to start/stop the dashboard, regenerate the API client, or something has gone wrong.
For "how is this designed" go to [`02_ARCHITECTURE.md`](02_ARCHITECTURE.md); Phase 1's pipeline
has its own runbook in the sibling `danger-zone` checkout.

The dashboard is **read-only and stateless**: it computes everything on demand from the Phase 1
SQLite file and caches in-process. The right answer to most "is it wrong?" questions is "restart
it" — nothing it does can corrupt data.

---

## At-a-glance triage

```bash
curl -s http://127.0.0.1:8800/health                 # liveness — expect {"status":"ok"}
curl -s http://127.0.0.1:8800/v1/meta | head -c 300  # data freshness + coverage
uv run dz-dashboard info                             # resolved config (DB path, bind, static dir)
```

If `/health` answers but pages look wrong, jump to [Numbers look wrong](#numbers-look-wrong).
If `/health` doesn't answer, jump to [The dashboard won't start](#the-dashboard-wont-start).

---

## Start / stop

There are three ways to run, by use case.

### Development (two processes, hot reload)

```bash
make dev          # BFF on :8800 (reload) + Vite dev server on :5173; Ctrl-C stops both
```

Open **http://127.0.0.1:5173**. Vite proxies `/v1`, `/health`, `/openapi.json` to the BFF, so
the browser talks to one origin. Edit Python → uvicorn reloads; edit `web/` → Vite hot-reloads.

If you'd rather run them by hand (two terminals):

```bash
uv run dz-dashboard serve --reload     # terminal 1
cd web && npm run dev                  # terminal 2
```

### Production-ish (one process, single origin) — for daily use

```bash
make serve        # builds web/dist, then runs ONE uvicorn that serves API + SPA on :8800
```

Open **http://127.0.0.1:8800**. There is no second server and no CORS: the BFF serves the built
SPA from `web/dist` (deep links fall back to `index.html`; `/v1` routes always win). Equivalent to:

```bash
cd web && npm run build
uv run dz-dashboard serve --static web/dist
```

### Always-on (survives logout / reboot)

Use the systemd **user** service (preferred) or the cron `@reboot` entry — pick one, see
[`scripts/dz-dashboard.service`](../scripts/dz-dashboard.service) and
[`scripts/cron.example`](../scripts/cron.example) for the install steps. Quick reference once
installed:

```bash
systemctl --user restart dz-dashboard.service
systemctl --user status  dz-dashboard.service
journalctl --user -u dz-dashboard.service -f       # follow logs
```

Stop a foreground run with Ctrl-C; stop the service with `systemctl --user stop dz-dashboard.service`.

---

## Regenerate the typed API client

The frontend's types in `web/src/lib/api/schema.d.ts` are **generated** from the BFF's OpenAPI
document — never hand-edited. Regenerate after any BFF contract change (new/changed endpoint or
response shape):

```bash
uv run dz-dashboard serve            # BFF must be running on :8800
make gen-api                         # == cd web && npm run gen:api
cd web && npm run typecheck          # every stale call site now fails to compile
```

To check for drift without writing (what CI runs):

```bash
cd web && npm run gen:api:check      # diffs the live schema against the committed client
```

If `typecheck` breaks after a regen, that's the contract doing its job: fix the call sites to
match the new schema; never edit `schema.d.ts` by hand.

---

## The ff-pipeline dependency (path vs pinned git)

`ff_dashboard` imports `ff_pipeline.repository` for DB access. The source is declared in
`pyproject.toml` under `[tool.uv.sources]`:

- **Active (local dev):** an editable path to the sibling checkout, `../danger-zone`. This is
  the package that produced the live DB, so the ORM models always match the on-disk schema.
- **Reproducible / CI:** swap to a pinned git tag so a build doesn't depend on a sibling working
  tree:

  ```toml
  [tool.uv.sources]
  ff-pipeline = { git = "ssh://git@github.com/ocmooch/danger-zone.git", tag = "v1.2.0" }
  ```

  After swapping, run `uv lock && uv sync --extra dev`. The DB schema the tag produces must match
  the `DATABASE_URL` you point at, or you'll see the schema-mismatch symptoms below. The current
  live DB requires the ≥1.2.0 schema with team/owner avatar columns, so the fallback example is
  pinned to `v1.2.0` (the earliest tag that carries those columns); bump it whenever the live DB is
  regenerated from a newer pipeline release.

---

## Common breakages

### The dashboard won't start

| Symptom | Cause | Fix |
|---|---|---|
| `Address already in use` on :8800 | a previous run (or the service) is still bound | `systemctl --user stop dz-dashboard.service`, or find it: `ss -ltnp \| grep 8800` and kill it; or run on another port: `dz-dashboard serve --port 8801` (update `web/vite.config.ts` proxy + the service to match) |
| `ModuleNotFoundError: ff_pipeline` | deps not installed, or the sibling checkout moved | `make install` (`uv sync --extra dev`); confirm `../danger-zone` exists or switch to the pinned git source above |
| Exits immediately, no error | wrong working directory for a relative `DATABASE_URL` | paths resolve against the project root regardless of CWD; run `uv run dz-dashboard info` to see the resolved DB path |

### Data endpoints return 503 `service_unavailable`

The DB has no completed pipeline run (or the file is missing). This is honest, not a bug — the
dashboard refuses to invent data. `/health` and `/v1/meta` still answer 200 (meta reports the
empty coverage), so use them to confirm: run `dz-dashboard info` for the resolved path, check
the file exists, and run the Phase 1 pipeline in the sibling repo until `pipeline_runs` has a
success row.

### A view shows a gap banner / "not scored" instead of numbers

Also expected. Documented gaps (an unscored current/in-progress season, current-season-only
availability, a genuinely-missing DST team/week row) surface as `available:false` and render a
`DataGap`, never a fake `0`. Per-player fantasy scoring now spans 2010–2025 since F-51; the
unscored-season affordance is driven by the per-season `is_scored` flag. DST is otherwise scored
end-to-end. Verify against `/v1/meta` coverage. Only worry if a season `/v1/meta` reports as
*scored* (and `dst_scoring_complete:true`) shows a gap where data should exist.

### Numbers look wrong

1. Confirm freshness: `curl -s http://127.0.0.1:8800/v1/meta` — the `pipeline_run_id` and
   coverage should match the latest Phase 1 run.
2. Bust the in-process cache by restarting the BFF (it's keyed on `pipeline_run_id`; a new run
   invalidates it automatically, but a restart forces a clean recompute).
3. If still wrong, it's an analytics bug, not an ops issue: the math lives in
   `src/ff_dashboard/analytics/` with unit tests — reproduce against the fixture DB
   (`uv run pytest -k <metric>`).

### Frontend can't reach the API / blank page

- **Dev:** the BFF isn't running, or Vite's proxy target drifted. Start the BFF; check
  `web/vite.config.ts` points at `http://127.0.0.1:8800`.
- **Production-ish:** you're hitting a *stale* `web/dist`. Rebuild: `make build-web` (or
  `make serve`, which builds first).

### `typecheck` fails right after pulling

The committed API client is out of sync with the schema (contract drift). Start the BFF and
`make gen-api`, then fix the flagged call sites. See
[Regenerate the typed API client](#regenerate-the-typed-api-client).

### Playwright e2e won't run

The browser binaries aren't installed (separate from `npm ci`):

```bash
cd web && npx playwright install chromium
make test-e2e
```

If snapshots fail on a legitimate UI change, refresh them: `make e2e-update`, then review the diff.

---

## The green gate (before any commit)

```bash
make check        # backend: pytest + ruff check + mypy; frontend: typecheck + test
```

e2e/visual-regression run separately (they boot real servers): `make test-e2e`.
