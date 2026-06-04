# Handoff prompt template — review fix-pass session

Reusable, near-turnkey prompt for executing one fix-pass from
`docs/plans/REVIEW_FIXES_ROADMAP.md` (findings in `docs/reviews/2026-06-in-browser-review.md`).

**How to use:** copy the block below, set the two variables, paste as the session prompt.
- `PASS_ID` — `P1`…`P6` (or a `UP` sub-program).
- `STAGE` — `PLAN`, `BUILD`, or `VERIFY`. Run them in that order, one thread each (token-budget
  discipline). **Fast path:** for a small pass (≤ ~3 findings, one layer, no contract change) set
  `STAGE = ALL` to plan→build→verify in a single thread.

Nothing else is required from you per stage — the agent self-serves from the roadmap + review doc.

---

```
ROLE: Execute fix-pass {{PASS_ID}}, stage {{STAGE}}, from the 2026-06 review-fixes program.
This is a BUILD program governed by CLAUDE.md's session model and token budget. Be surgical:
read only what this pass cites; don't re-explore the tree.

READ FIRST (in this order, then stop):
1. docs/plans/REVIEW_FIXES_ROADMAP.md — the row for {{PASS_ID}}: deps, findings, status, and any
   "Inputs only you can supply" this pass needs. If a needed input is still ☐ pending, proceed
   config-driven with a seeded default and leave a TODO keyed to it (do NOT block; note it).
2. docs/reviews/2026-06-in-browser-review.md — the "### {{PASS_ID}} —" section under
   "Proposed fix passes" (authoritative scope/files/signatures/tests/Done-when) AND each finding
   it lists (F-NN entries) for the evidence and suspected locations.
3. PROGRESS.md — current state.
4. ONLY the docs/0X_*.md sections the pass touches (use the CLAUDE.md doc map; read the section,
   not the file). Per-milestone hints still apply (e.g. analytics → 04; a page → 07).
Do not read generated/lock/vendor files (web/src/lib/api/schema.d.ts, *-lock, node_modules, dist).
For the API surface, run `npm run gen:api` + the drift check — never read the schema.

STANDARDS & PROTOCOLS (hard rules — never violate):
- Git: work on `feature/fix-{{PASS_ID}}-<short-name>` cut from `dev`; PR to `dev` only; delete the
  branch (local + remote) after merge confirms. Never commit to dev/main directly.
- Commit trailers (every commit): AI-Model / Prompted-By / Reviewed-By. NEVER Co-Authored-By: Claude.
- Read-only DB: no INSERT/UPDATE/DELETE; only ff_pipeline.repository (+ pure scoring helpers).
  If the fix truly needs to mutate source data, it is OUT OF SCOPE here → it belongs to UP /
  ff-pipeline; record it as a UP item and stop at the dashboard boundary.
- No metric math in web/ — all math in ff_dashboard/analytics/. Never hand-edit web/src/lib/api/;
  change the BFF schema and run `npm run gen:api`.
- Honesty: never render 0/dash for missing data — use available:false / DataGap. Keep the
  raw-vs-scored coverage truth in mind (team totals/standings/rosters/drafts exist 2010–2015;
  per-player fantasy scoring does not).

STAGE — do only this stage's work:
- PLAN: write docs/plans/fix-{{PASS_ID}}-<name>.md — concrete scope, exact files to touch,
  metric/endpoint/component signatures, the test list, and "Done when" (lifted + sharpened from the
  review doc). No implementation. Commit the plan. End well under the limit.
- BUILD: implement against the plan. Analytics/data before the views that render them. Add/extend
  the tests from the plan as you go. Iterate with the ONE scoped test file you're touching (quiet
  flags); do NOT run the full gate here. Update PROGRESS.md as you go. If context tightens, commit a
  checkpoint, write the next step into PROGRESS.md, and stop for a fresh thread.
- VERIFY: run the green gate ONCE via the green-gate skill (backend pytest+ruff+mypy; frontend
  gen:api drift + typecheck+lint+vitest; e2e only if the pass calls for it). Read only failures,
  fix them. Open the affected view(s) and click through. Then commit + open the PR.
- ALL (fast path only): PLAN→BUILD→VERIFY in one thread for a small single-layer pass.

SURFACE CONSIDERATIONS (don't silently absorb):
- If you discover a new issue, a scope change, a cross-pass dependency, or a decision the user must
  make, APPEND one line to the roadmap's "Considerations surfaced during the build" log
  (`- [{{PASS_ID}}, <date>] <observation> → <impact>`). If it's a genuine new finding, also add an
  F-NN entry to the review doc and assign it a pass. Then continue the planned work.

DOCUMENTATION & HOUSEKEEPING (part of "done", not optional):
- Update any docs/0X_*.md the change affects (a new endpoint → 05; a new metric → 04; a page → 07).
- Update PROGRESS.md (Current state / Next / Files that matter now).
- Tick {{PASS_ID}} status in docs/plans/REVIEW_FIXES_ROADMAP.md (◐ on BUILD, ☑ on merge); mark any
  resolved finding in the review doc with its PR.
- Tests: the pass's test list exists and passes; coverage doesn't regress.
- After the PR merges: delete the feature branch (local + remote).

DONE WHEN:
- The "{{PASS_ID}} Done when" from the review doc is satisfied AND the full gate is green AND the
  affected view(s) were opened and clicked through AND docs/PROGRESS/roadmap are updated AND the PR
  to `dev` is open with trailers. (For PLAN: the plan doc is committed and the row references it.)

DO NOT: touch another pass's findings; change API response shapes beyond what the pass's plan
states; hand-edit the generated client; run the full gate during BUILD; read lock/vendor/generated
files; over-read source — grep for the symbol, open the matching span only.
```

---

## Notes for the human driver

- **Pick passes top-down** from the roadmap status table, respecting `Depends on`. P1 first.
- **Supply the inputs** in the roadmap's "Inputs only you can supply" table when a pass needs them;
  otherwise the pass proceeds with seeded defaults + a TODO and you can backfill later.
- **UP items aren't dashboard PRs** — they're Phase-1 programs in `ff-pipeline`; use the
  `players-audit-danger-zone.md` handoff as the model and run them with the same template idea
  pointed at that repo.
- Want it even more automated? This template can be wrapped as a `fix-pass-session` skill (sibling
  to `milestone-session`/`green-gate`) so `STAGE`/`PASS_ID` become skill args — ask and it's a small
  add.
