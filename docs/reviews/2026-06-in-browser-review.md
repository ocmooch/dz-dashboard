# In-browser review — 2026-06

**Purpose:** systematic click-through of the dz-dashboard SPA against the real Phase 1 DB to
surface data gaps, honesty-affordance violations, and UX/presentation bugs.

**Method — observe-only.** This session records findings; it does **not** fix code, run the
gate, or touch CI. Fixes are deferred to a small number of batched fix-passes downstream
(see "Proposed fix passes"), each its own PLAN→BUILD→VERIFY thread with a single gate + CI
run. This batching is deliberate: it prevents the piecemeal refactor/test/lint/CI churn that
makes on-the-spot fixing expensive.

**Triage shortcut (don't deep-read source):** to pin a finding's layer, hit the BFF directly
(`curl -s http://127.0.0.1:8800/v1/...`) and compare the JSON to the screen.
- Wrong/absent in the API response → `data` / `analytics` / `api-contract`.
- Correct in API but wrong on screen → `frontend-presentation`.
- Bare `0` / dash where data is absent → `gap-affordance` (must be `DataGap`).

---

## Coverage checklist

Tick each view as it's walked. Probe known gap zones: unscored 2010–2015,
current-season-only availability, partial DST, seasons without captured drafts.

- [ ] home
- [ ] standings (+ timeline, week-stepper)
- [ ] managers — index
- [ ] managers — profile (trophy case, trajectory, season table, rivalry snapshot)
- [ ] matchups — week grid (+ week-stepper)
- [ ] matchups — box score (optimal lineup, left-on-bench, expandable breakdowns)
- [ ] records
- [ ] rivalries — matrix
- [ ] rivalries — pairwise
- [ ] players — index (search / filter)
- [ ] players — detail (scoring chart, ownership timeline, availability)
- [ ] stats
- [ ] teams (roster-by-week, schedule, scoring trend, transactions)
- [ ] draft
- [ ] power
- [ ] search
- [ ] about / coverage

---

## Findings

<!--
Copy this template per finding. Keep entries terse; evidence is a curl snippet or a one-line
response excerpt, not a paragraph.

### F-NN — <short title>
- View/route:
- Observed:
- Expected:
- Severity: blocker | major | minor | polish
- Layer: data | analytics | api-contract | frontend-presentation | gap-affordance
- Evidence: <curl snippet / response excerpt / screenshot path>
- Suspected location: <one file:symbol, if known — unverified>
- Batch: <assigned at end>
-->

_None logged yet._

---

## Proposed fix passes

_Filled in at end of the review session. Group findings into 2–4 coherent batches by
layer + theme; one batch = one PR, gate run once. Order by dependency (data/analytics before
the views that render them). For each batch capture: scope, files likely touched,
metric/endpoint/component signatures, test list, and "Done when" — this seeds each batch's
PLAN session._

Precedent for triage→ship-in-passes: `docs/plans/players-audit-dashboard.md` +
`docs/handoffs/players-audit-danger-zone.md`.
