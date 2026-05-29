# web/ — Danger Zone dashboard SPA

Pure-presentation React + TypeScript single-page app. It holds **no business
logic** — every number is computed by the `ff_dashboard` BFF and rendered here.
The API client (`src/lib/api/schema.d.ts`) is **generated** from the BFF's
OpenAPI document; never hand-edit it — change the BFF and regenerate.

## Stack

Vite · React 18 · TypeScript · Tailwind (token-driven) · TanStack Query ·
React Router · openapi-fetch + openapi-typescript · Recharts.

## Run (dev)

```bash
# 1) start the BFF (from the repo root)
uv run dz-dashboard serve            # http://127.0.0.1:8800

# 2) start the SPA (from web/)
npm install
npm run dev                          # http://127.0.0.1:5173
```

The Vite dev server proxies `/v1`, `/health`, and `/openapi.json` to the BFF, so
the browser only ever talks to one origin.

## Regenerate the typed client (after any BFF contract change)

```bash
npm run gen:api    # reads http://127.0.0.1:8800/openapi.json -> src/lib/api/schema.d.ts
```

CI regenerates and diffs this file, so contract drift cannot merge.

## Checks

```bash
npm run typecheck
npm run build
```

## Design

The visual language ("Danger Zone" HUD: near-black instrument panels,
afterburner-orange accent, mono/tabular numerics) lives in
`src/styles/tokens.css` and `src/design-system/`. See `docs/06_DESIGN_SYSTEM.md`.
Pages are disposable compositions of the durable primitives.

## Status (first look)

This is the P3 frontend bootstrap as a first look: app shell (top bar, global
season switcher, data-as-of indicator, left nav), the generated typed client,
and three real wired pages — **Home** (command center), **Standings**, and
**Records book** — reading the live BFF, with honest `DataGap` affordances.
Remaining nav destinations land in later milestones (P5–P9).
