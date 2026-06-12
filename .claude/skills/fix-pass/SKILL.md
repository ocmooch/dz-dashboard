---
name: fix-pass
description: Execute one fix-pass from the 2026-06 review-fixes program (docs/plans/REVIEW_FIXES_ROADMAP.md). Invoke as `/fix-pass <PASS> [STAGE]` — e.g. `/fix-pass P1 plan`, `/fix-pass P3 build`, `/fix-pass P2 verify`, `/fix-pass P4` (auto-stage), or `/fix-pass P5 all` (small pass, one thread). Drives a PLAN→BUILD→VERIFY fix-pass against the 48 in-browser-review findings with all project standards, tests, docs, and housekeeping. Use whenever the user types `/fix-pass` or asks to "start/continue fix-pass P{N}".
---

# Fix-pass session (token-cheap, near-turnkey)

Executes one pass (`P1`–`P6`, or a `UP` sub-program) of the program in
`docs/plans/REVIEW_FIXES_ROADMAP.md`. Findings live in `docs/reviews/2026-06-in-browser-review.md`.
Be surgical: read only what this pass cites; don't re-explore the tree.

## Parse the args

`/fix-pass <PASS> [STAGE]`
- **PASS** — `P1`…`P6` or `UP` (or a `UP-F27`-style sub-program). Required. If missing, read the
  roadmap status table and propose the next unblocked pass, then ask the user to confirm.
- **STAGE** — `plan` | `build` | `verify` | `all`. Optional. If omitted, **infer**: no
  `docs/plans/fix-{PASS}-*.md` yet → `plan`; plan exists but findings unresolved / branch mid-work
  → `build`; build checkpoint says ready → `verify`. State the inferred stage in one line before
  starting. `all` = PLAN→BUILD→VERIFY in one thread; only for a small pass (≤ ~3 findings, one
  layer, no API-contract change).

> Fix-pass `P1`–`P6` are **distinct** from milestone `P0`–`P11` in `docs/09_ROADMAP.md`.

## Entry — ~4 cheap reads, then stop

1. `docs/plans/REVIEW_FIXES_ROADMAP.md` — the `{PASS}` row: deps, findings, status, and the
   "Inputs only you can supply" table. If a needed input is still ☐ pending, **don't block** —
   proceed config-driven with a seeded default and leave a `TODO(input: …)` keyed to it.
2. `docs/reviews/2026-06-in-browser-review.md` — the `### {PASS} —` section under "Proposed fix
   passes" (authoritative scope/files/signatures/tests/Done-when) **and** each `F-NN` it lists
   (evidence + suspected locations).
3. `PROGRESS.md` — current state.
4. ONLY the `docs/0X_*.md` **sections** this pass touches (CLAUDE.md doc map; section, not file).

Never read generated/lock/vendor files (`web/src/lib/api/schema.d.ts`, `*-lock`, `node_modules`,
`dist`, `htmlcov`). For the API surface run `npm run gen:api` + the drift check — never read the schema.

## Standards & protocols (hard rules)

- **Git:** branch `feature/fix-{PASS}-<short-name>` cut from `dev`; PR to `dev` only; delete branch
  (local + remote) after merge confirms. Never commit to `dev`/`main` directly.
- **Trailers** on every commit: `AI-Model` / `Prompted-By` / `Reviewed-By`. NEVER `Co-Authored-By: Claude`.
- **Read-only DB.** No INSERT/UPDATE/DELETE; only `ff_pipeline.repository` (+ pure scoring helpers).
  If a fix needs to mutate source data it is OUT OF SCOPE → record it as a `UP` item and stop at the
  dashboard boundary.
- **No metric math in `web/`** (all math in `ff_dashboard/analytics/`). Never hand-edit
  `web/src/lib/api/`; change the BFF schema and run `npm run gen:api`.
- **Honesty:** never render `0`/dash for missing data — `available:false` / `DataGap`. Hold the
  coverage truth: team totals/standings/rosters/drafts exist 2010–2015; per-player fantasy scoring
  does not (`player_stats_scored` = 2016–2025).

## Stage — do only this stage

### PLAN
Read only the doc sections the pass cites. Write `docs/plans/fix-{PASS}-<name>.md`:
- Scope + the verbatim "Done when" (from the review doc, sharpened).
- Exact files to create/touch (paths).
- Each metric: function signature + known-answer test cases (incl. a gap case).
- Each endpoint: route + response shape (name the schema; don't paste the contract).
- Each view: which primitives compose it.
No implementation. Commit the plan; set the roadmap row's Plan-doc + status ◐. End well under the limit.

### BUILD
Implement against the plan, **analytics/data before the views that render them**. Add/extend the
plan's tests as you go. Iterate with the **one** scoped test file you're touching (quiet flags) —
do **not** run the full gate here. Update `PROGRESS.md`. If context tightens: commit a checkpoint,
write the next step into `PROGRESS.md`, stop for a fresh thread.

### VERIFY
Run the gate **once** via the `green-gate` skill (backend pytest+ruff+mypy; frontend gen:api drift
+ typecheck+lint+vitest; e2e only if the pass calls for it). Read only failures; fix them. Open the
affected view(s) and click through. Then commit + open the PR to `dev` with trailers.

### ALL (fast path)
PLAN→BUILD→VERIFY in one thread for a small single-layer pass.

## Surface considerations (don't silently absorb)

Discover a new issue, scope change, cross-pass dependency, or a decision the user must make →
append one line to the roadmap's **"Considerations surfaced during the build"** log
(`- [{PASS}, <date>] <observation> → <impact>`). If it's a genuine new finding, also add an `F-NN`
entry to the review doc and assign it a pass. Then continue the planned work.

## Documentation & housekeeping (part of "done")

- Update any `docs/0X_*.md` the change affects (endpoint → 05; metric → 04; page → 07).
- Update `PROGRESS.md` (Current state / Next / Files that matter now).
- Tick `{PASS}` status in the roadmap (◐ on BUILD, ☑ on merge); mark each resolved finding in the
  review doc with its PR number.
- Tests in the pass's list exist and pass; coverage doesn't regress.
- After merge: delete the feature branch (local + remote).

## Done when

The "{PASS} Done when" from the review doc is satisfied **and** the full gate is green **and** the
affected view(s) were clicked through **and** docs/PROGRESS/roadmap are updated **and** the PR to
`dev` is open with trailers. (PLAN: the plan doc is committed and the roadmap row references it.)

## Never

Touch another pass's findings; change API response shapes beyond the plan; hand-edit the generated
client; run the full gate during BUILD; read lock/vendor/generated files; over-read source (grep
the symbol, open the matching span only).
