# Phase 2 — Claude Code Kickoff

Copy/paste the prompt below into a fresh Claude Code session in the Phase 1 repo to start
Phase 2. As in Phase 1, run one long session per milestone (the milestones in
`docs/09_ROADMAP.md` are sized to fit).

> **Before you start:** work through `prerequisites.md` and answer the sign-off questions in
> `docs/10_OPEN_QUESTIONS.md`. Paste your answers into the kickoff so Claude Code builds the
> stack/visual direction you actually want, not the defaults.

---

## Step 1 — Prep

```bash
cd ~/code/fantasy-football
git checkout dev && git pull && git checkout -b feature/phase-2-dashboard
ls docs/                              # Phase 2 docs present alongside Phase 1's
sqlite3 data/fantasy.db ".tables"     # confirm the DB is populated
uv sync && node --version
```

## Step 2 — Start Claude Code

```bash
claude
```

## Step 3 — Paste the first-session kickoff (P0 + P1 + P2)

```
>>>
I'm starting Phase 2 (the analytics dashboard) of my personal fantasy football system.
Phase 1 (the data pipeline) is complete and lives in this repo. The Phase 2 design package
is in docs/ — read it in order before writing code:

  docs/01_SPEC.md           docs/06_DESIGN_SYSTEM.md
  docs/02_ARCHITECTURE.md   docs/07_PAGES_AND_VIEWS.md
  docs/03_DATA_ACCESS.md    docs/08_TESTING_STRATEGY.md
  docs/04_ANALYTICS_MODEL.md docs/09_ROADMAP.md
  docs/05_API_CONTRACT.md   docs/10_OPEN_QUESTIONS.md

Also re-read the Phase 1 docs you need for context: docs/04_DATA_MODEL.md (the schema you'll
read), docs/06_API_CONTRACT.md (the envelope conventions to mirror), and CONTRIBUTING.md (git
model + AI commit trailers).

Phase 2 is two new things in this repo plus a contract between them:
  1. ff_dashboard — a read-only analytics backend-for-frontend (Python/FastAPI) that imports
     ff_pipeline.repository and computes all derived metrics server-side.
  2. web/ — a React + TypeScript SPA that is PURE PRESENTATION (no business logic), calling
     only the ff_dashboard API via a client generated from its OpenAPI schema.

MY DECISIONS on the open questions (overrides the doc defaults where stated):
  • Q1 data access: <BFF reusing repository | browser-only>
  • Q2 frontend stack: <confirm React+TS+Vite+Tailwind+TanStack Query+React Router+Recharts | swaps>
  • Q3 visual direction: <"Danger Zone" HUD dark | other>
  • Q4 view priority: <confirm default | reorder>
  • Q5 standings tiebreaker: <wins then points-for | actual order>
  • Q7 lineup slots (for optimal-lineup): <where the slot config is / the slot list>
  (others: use the doc defaults unless I say otherwise)

This session: complete milestones P0, P1, P2 from docs/09_ROADMAP.md:
  P0 — confirm Phase 1 data readiness (reconstruction done; 2016–2025 scored; matchups all weeks)
  P1 — ff_dashboard bootstrap (settings, read-only WAL DB reuse, /health + /v1/meta, cache)
  P2 — analytics core for data-ready metrics (standings, owners-career, head-to-head, records,
       players) with the fixture database, unit tests, and their endpoints + contract tests

Critical implementation notes:
  • Same toolchain as Phase 1: uv, ruff, mypy --strict, pytest, structlog. Green gate before commit:
      uv run pytest && uv run ruff check && uv run mypy src/
  • ff_dashboard goes under src/ff_dashboard/ exactly as docs/02_ARCHITECTURE.md specifies.
  • READ-ONLY: open the DB in WAL + read-only/busy_timeout mode. No INSERT/UPDATE/DELETE,
    no imports of upsert/crawler/normalizer/scoring-write code. Only ff_pipeline.repository
    (and pure ff_pipeline.scoring helpers if needed for display).
  • Mirror Phase 1's API envelope ({data, meta}) and error shape exactly (copy _meta.py/errors.py).
  • Be HONEST about data gaps (docs/03 + N2.2): unscored 2010–2015, current-season-only
    availability, incomplete DST scoring → endpoints return available:false (never 0).
  • Build the fixture DB first (docs/08) with KNOWN answers incl. gap cases; test against it.
  • Don't add the frontend yet — that's P3. Backend + tests only this session.

Proceed step by step. Verify each milestone's "Done when" before moving on. Commit at the end
of each milestone with the Phase 1 trailer format. Start by reading the docs and giving me a
brief summary + any clarifying questions before writing code.
<<<
```

---

## Subsequent sessions (P3+)

```
>>>
Continuing Phase 2 of the fantasy football dashboard.

Today: milestone P{N} from docs/09_ROADMAP.md ({MILESTONE_NAME}).

Please:
1. Read docs/09_ROADMAP.md to confirm P{N} scope + "Done when"
2. Read the relevant deeper docs (P3→06_DESIGN_SYSTEM; P5→04_ANALYTICS_MODEL §3 + 05/07;
   P6→04 §4–7; etc.)
3. Review existing code (ff_dashboard and web/) to understand current state
4. Implement, holding the boundaries: frontend has NO business logic; the API client is
   generated from /openapi.json; everything reads the BFF only
5. Add tests (analytics unit / contract / component / e2e as the milestone calls for)
6. Run the full gate (backend: pytest+ruff+mypy; frontend: lint+typecheck+test) before done
7. Commit with the Phase 1 trailer format

Start with a brief plan.
<<<
```

---

## Sanity checks per session

Backend:
- [ ] `uv run pytest tests/dashboard` green
- [ ] `uv run ruff check` / `ruff format --check` clean
- [ ] `uv run mypy src/ff_dashboard` clean
- [ ] no write operations / no forbidden imports (grep for `upsert`, `INSERT`, crawler modules)

Frontend (P3+):
- [ ] `npm run gen:api` produces no diff (client in sync with schema)
- [ ] `npm run typecheck` / `npm run lint` clean
- [ ] `npm run test` green; e2e green where applicable

Both:
- [ ] the milestone's "Done when" in `docs/09_ROADMAP.md` is satisfied
- [ ] you've opened the new view(s) in a browser and clicked through
- [ ] committed with `AI-Model` / `Prompted-By` / `Reviewed-By` trailers (never `Co-Authored-By: Claude`)

## What I expect Claude Code NOT to do

- Don't put any derived-metric math in the frontend — it belongs in `ff_dashboard/analytics/`.
- Don't write to the database, ever. Don't import Phase 1 write/crawler code.
- Don't hand-edit the generated API client — change the BFF schema and regenerate.
- Don't render 0 where data is missing — use the `DataGap` affordance / `available:false`.
- Don't change Phase 1 code except additive, read-only query helpers in repository/queries.py.
- Don't default the frontend fonts to Inter/Roboto/Arial — pick distinctive faces (docs/06).
- Don't merge milestones — finish each cleanly.

## Useful mid-session prompts

- **Verifying a metric:** "Pull the raw rows behind this records-book number and show the
  computation step by step so I can hand-check it against NFL.com."
- **A chart looks off:** "Show me the exact data array passed to this chart and the
  chartTheme tokens it's using."
- **Contract drift:** "Regenerate the API client from /openapi.json and list every call site
  the schema change broke."
- **A new view I want:** "I want a '{X}' view. Propose the analytics function + endpoint +
  which existing primitives compose the page, before writing anything."

## When done with Phase 2

Open the Phase 3 design conversation. Phase 3 (AI-assisted GM decision support) will read the
same BFF/API and add recommendation logic — the dashboard you built becomes the surface those
recommendations render into.
