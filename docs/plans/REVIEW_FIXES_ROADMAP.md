# Review-Fixes Roadmap — executing the 2026-06 in-browser review

The execution tracker for the fix program seeded by `docs/reviews/2026-06-in-browser-review.md`
(48 findings, F-01–F-48). This file is the **single source of truth for "which fix-pass is next."**
It does **not** restate findings — it points at them. Read this + the cited findings, not the tree.

> **Naming, to avoid collision:** the review groups findings into **fix-passes P1–P6 + UP**. These
> are *fix-pass* numbers and are **distinct** from the Phase-2 *milestone* numbers P0–P11 in
> `docs/09_ROADMAP.md`. When in doubt write "fix-pass P2" vs "milestone P5".

## How to run this (lightweight, near-turnkey)

The heavy thinking is already done — in the review doc and here. Per pass, the loop is:

1. Pick the **next unblocked pass** from the status table (top-down; respect `Depends on`).
2. Run the **`/fix-pass` skill**: `/fix-pass <PASS> [STAGE]` — e.g. `/fix-pass P1 plan`, then
   `/fix-pass P1 build`, then `/fix-pass P1 verify` (one thread each, token-budget discipline).
   Omit the stage (`/fix-pass P1`) to auto-infer it; use `/fix-pass P1 all` for a small pass. The
   skill encodes the same workflow as the handoff template — that template is the manual fallback.
3. Review the PR it opens to `dev`, merge, done. The agent handles branch, tests, docs, trailers,
   status ticks, and surfaces any new considerations back into this file.

Your only recurring jobs: **pick the next pass, supply the inputs below when a pass needs them, and
review/merge the PR.** Everything else is automated by the template.

## Inputs only you can supply (unblock passes up front)

Resolve these once and record them here so no pass stalls mid-build. Until filled, the dependent
pass proceeds **config-driven with seeded defaults** and leaves a TODO keyed to the input.

| Input | Needed by | Status | Value (fill in) |
|-------|-----------|--------|-----------------|
| Season-length switch year(s): regular 1–13 → 1–14; playoffs/championship week shift | P1 (F-32) | ☐ pending | _e.g. "switched in 20NN"_ |
| Waiver standard-order → **FAAB** switch point | P4 / UP (F-37) | ☐ pending | _year/season_ |
| Ownership-succession history (which owner held which team, which seasons) | UP (F-06) | ☐ pending | _source / table_ |
| Pre-2016 scoring reconstruction: go / sequencing | UP (F-27) | ☐ pending | _go-ahead + priority_ |

## Status

Key: ☐ todo · ◐ in progress · ☑ merged · ⊘ blocked (needs an input above)

| Pass | Title | Primary layer | Depends on | Findings | Status | Plan doc |
|------|-------|---------------|------------|----------|--------|----------|
| **P1** | Analytics correctness, scoping & enrichment (incl. season-structure model) | analytics + api | — (season model config-driven) | F-32, F-22, F-31, F-10, F-12, F-23, F-17, F-13 | ◐ (VERIFY done; **PR #30** open → dev) | `docs/plans/fix-P1-analytics.md` |
| **P2** | Data honesty & affordance precision (+ gap-validation harness) | gap-affordance + tests | soft: P1 (week semantics) | F-16, F-35, F-26, F-33, F-48, F-43 | ◐ (PLAN done) | `docs/plans/fix-P2-honesty.md` |
| **P3** | Search: scope, teams, hardening | data/analytics + api + tests | — | F-44, F-45, F-47 | ☐ | `docs/plans/fix-P3-search.md` |
| **P4** | Transactions (dashboard roster-diff tier) | analytics + api + frontend | — | F-37 (tier 1) | ☐ | `docs/plans/fix-P4-transactions.md` |
| **P5** | Frontend: navigation & presentation fixes | frontend | P1 (data it renders) + F-24 contract | F-34, F-36, F-05, F-24, F-07, F-15, F-46, F-14, F-11, F-40, F-30, F-04, F-28, F-02, F-42 | ☐ | `docs/plans/fix-P5-frontend-fixes.md` |
| **P6** | Frontend: composition, seasonality & insight enhancements | frontend | P1, P4, P2 | F-01, F-29, F-08, F-03, F-09, F-18, F-38, F-21, F-41 | ☐ | `docs/plans/fix-P6-frontend-insights.md` |
| **UP** | Upstream / Phase-1 program & research (NOT dashboard PRs) | data (pipeline) + research | runs alongside | F-27, F-25, F-37 (tier 2), F-06 | ☐ | per-program handoffs in `docs/handoffs/` |

### Recommended sequencing

```
P1 ──┬──────────────► P5 ──► P6
     │                 ▲      ▲
P2 ──┤(parallel)       │      │
P3 ──┤(parallel)       │      │
P4 ──┴─────────────────┘──────┘
UP  ════ runs in parallel as a separate Phase-1 program; its outputs (esp. F-27, F-25)
        retire several dashboard findings when they land — re-check this roadmap after each UP win.
```

P1 ships first (others render/consume its outputs). P2/P3/P4 are independent and can run in any
order or in parallel. P5 then P6 land the frontend once their data exists. UP is out-of-repo
(`ff-pipeline`) and asynchronous.

## Per-pass detail

Each row's **scope / files / signatures / test list / Done-when** already lives in the review doc's
**"Proposed fix passes"** section under the matching `### P{N}` heading — that is the authoritative
spec; do not duplicate it. The PLAN stage expands it into `docs/plans/fix-P{N}-*.md`. Quick anchors:

- **P1** — review doc § "P1 — Analytics correctness, scoping & enrichment". Build the per-season
  schedule model first (config-driven), then the scoping/enrichment fixes that consume it.
- **P2** — review doc § "P2 — Data honesty & affordance precision". The gap-validation harness
  (F-43) is the safety net; write it so it would have caught F-16/F-22/F-25/F-31/F-35.
- **P3** — review doc § "P3 — Search". League-scope the player branch; team synonyms +
  players-by-team + fantasy-team names; injection/regex/XSS tests.
- **P4** — review doc § "P4 — Transactions". Roster-diff derivation only; nfl.com scrape + FAAB
  are UP.
- **P5** — review doc § "P5 — Frontend: navigation & presentation fixes". Includes the F-24
  contract change (`scope`/`has_scored` removal) → run `gen:api` + drift check.
- **P6** — review doc § "P6 — Frontend: composition, seasonality & insight enhancements". Build the
  shared **season-phase** helper (in-season vs off-season) once; F-01 and F-29 consume it.
- **UP** — review doc § "UP". Each item is its own Phase-1 program/handoff; mirror
  `docs/handoffs/players-audit-danger-zone.md`.

## Considerations surfaced during the build (append-only log)

Each pass appends here anything it discovered that changes scope, crosses into another pass, or
needs a decision — so passes inform each other and nothing is silently absorbed. Format:
`- [P{N}, YYYY-MM-DD] <observation> → <impact / which finding or pass it touches>`.

- [P1, 2026-06-04] F-31 season-totals aggregation lives in the **Phase-1** `ff_pipeline...queries.season_totals` (sibling repo) and sums all weeks with no cap → P1 owns a week-capped aggregation dashboard-side in new `analytics/stats.py` instead of touching Phase-1 (read-only boundary). → no contract change, but the route stops importing the Phase-1 query.
- [P1, 2026-06-04] Frontend hardcodes the blowout threshold (`margin >= 40`, `MatchupsPage.tsx:58`) — metric math in `web/`. P1 moves close/blowout thresholds to backend flags (`is_close`/`is_blowout`); the frontend swap to consume them is **P5** (F-13/F-14). → cross-pass: P5 must drop the hardcoded `>=40`.
- [P1, 2026-06-04] `made_playoffs` derivation (F-10) risks over-counting if consolation/toilet-bowl games are flagged `is_playoff=True`. BUILD resolves against the fixture; fallback gates on a `playoff_teams` count in the schedule model. → may add a field to the season-schedule model.
- [P1, 2026-06-04] **BUILD: F-10 caveat resolved cleanly** — `Matchup.is_consolation` exists in the Phase-1 model, so `made_playoffs` = "≥1 `is_playoff` AND NOT `is_consolation` game"; no `playoff_teams` field needed on the schedule model. → schedule model stays minimal.
- [P1, 2026-06-04] **BUILD: records payload gained `team_record_era`** (sorted years with team totals) alongside `scored_era`, so the UI can label each record's window honestly. Flows through `RecordsBook`'s `extra="allow"` (no declared-field churn). → P5/P6 may surface both eras on the records view.
- [P1, 2026-06-04] **BUILD: H2H contract** — `cumulative_margin_for_a` + `closest_meeting` are now **declared** schema fields (with a `H2HMeeting` model), while the pre-existing `most_lopsided_meeting`/`highest_scoring_meeting` still flow through `extra="allow"` (undeclared, as before). → P5 reads `closest_meeting` typed; the older meeting objects stay untyped unless a later pass declares them.
- [P1, 2026-06-04] **BUILD: fixture extended** (`tests/conftest.py`) — 2015 now has final ranks + a week-3 playoff bracket (one championship + one consolation game) and a beyond-championship 2017 scored week, to exercise the new derivations. KNOWN-safe (181 backend tests green). → future passes touching the fixture should preserve the 2015 bracket and the cmc 2017 wk4 cap row.
- [P1, 2026-06-04] **VERIFY: real-DB check surfaced new finding F-49** — `Matchup.is_consolation` is unpopulated (0 rows) and `is_playoff` is set on every post-season game, so all 12 teams look like they advanced each season. F-10 `made_playoffs` therefore can't be derived honestly for most seasons; the dashboard now returns `None` unless the season's bracket is a *proper subset* of the league (a few older seasons qualify). Guard shipped in `owners.py`; root cause is upstream → **F-49 assigned to UP** (populate `is_consolation`/`playoff_teams`). No dashboard change needed when UP lands. → `result` is unaffected.
- [P1, 2026-06-04] **VERIFY: real-DB confirmed F-22** — a pre-2016 game does take a team record on real data (`lowest_team_score` = 36.8 in **2011**), validating the era split end-to-end.
- [P2, 2026-06-04] **PLAN:** the gap affordance keys off season-level `is_scored` and the data it needs (`is_scored`, `first/last_rostered_season`, coverage `scored_year_min`) is already in the responses → P2 is **copy-precision + one new player-detail affordance (F-26) + the F-43 harness + an F-48 docstring/doc reconcile**, with **no API response-shape change** (`gen:api` drift stays clean). → keeps the pass small and contract-safe.
- [P2, 2026-06-04] Tests live flat under `tests/test_*.py`, not `tests/dashboard/` as CLAUDE.md's command examples imply; the F-43 harness is `tests/test_coverage_integrity.py`. → follow the actual layout, not the doc path.
- [P1, 2026-06-04] Git base: the roadmap + 48-findings doc + fix-pass skill are in **open PR #29** (→ dev), not yet on `dev`. The fix-P1 PLAN doc is committed onto `feature/in-browser-review-findings` (rides into dev via #29). **#29 must merge before `/fix-pass P1 build`** so the BUILD branch cuts cleanly from an up-to-date `dev`. → sequencing dependency for every fix-pass.

## Done when (the whole program)

- Every pass P1–P6 is ☑ merged to `dev`, its findings resolved, its plan doc on disk.
- The gap-validation harness (F-43) is green and asserts the coverage truths.
- `PROGRESS.md` reflects the post-review state; `docs/09_ROADMAP.md` unaffected (this is a separate
  program); the review doc's findings each show their resolving PR.
- UP items are tracked as Phase-1 programs with their own handoffs; this roadmap notes which
  dashboard findings each UP win retires.
