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
npm run typecheck     # tsc --noEmit
npm run test          # Vitest: design-system, charts, and feature/page tests
npm run build         # type-check + production build into dist/
```

## End-to-end + visual regression (Playwright)

e2e runs against a **real BFF bound to the test fixture database** (the same
known-answers DB the Python suite uses), serving the built SPA single-origin —
Playwright's `webServer` builds and boots it automatically.

```bash
npx playwright install --with-deps chromium   # first time only (browser + system deps)
npm run test:e2e                              # journeys + visual-regression
npm run test:e2e:update                       # refresh visual-regression baselines
```

`e2e/journeys.spec.ts` covers the critical paths (home/nav, standings, records →
source box score, points-left-on-bench, rivalry matrix, pre-2016 gap honesty);
`e2e/visual.spec.ts` snapshots the key pages with the live "data as of" timestamp
masked. Vitest is configured to ignore `e2e/` so the two runners don't collide.

## Design

The visual language ("Danger Zone" HUD: near-black instrument panels,
afterburner-orange accent, mono/tabular numerics) lives in
`src/styles/tokens.css` and `src/design-system/`. See `docs/06_DESIGN_SYSTEM.md`.
Pages are disposable compositions of the durable primitives.

## Status

Complete through P11. The app shell (top bar, global season switcher,
data-as-of indicator, left nav, global search) hosts the full set of wired
pages — Home, Standings, Power, Matchups + Box score, Rivalries (matrix +
pairwise), Records book, Players + detail, Stats, Draft, and Coverage/About —
all reading the live BFF through the generated typed client, with honest
`DataGap` affordances and no faked zeros. Covered by Vitest component/feature
tests and Playwright e2e + visual-regression.
