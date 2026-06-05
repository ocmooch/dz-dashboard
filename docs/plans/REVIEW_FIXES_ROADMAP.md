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
| **P1** | Analytics correctness, scoping & enrichment (incl. season-structure model) | analytics + api | — (season model config-driven) | F-32, F-22, F-31, F-10, F-12, F-23, F-17, F-13 | ☑ (**PR #30** merged → dev) | `docs/plans/fix-P1-analytics.md` |
| **P2** | Data honesty & affordance precision (+ gap-validation harness) | gap-affordance + tests | soft: P1 (week semantics) | F-16, F-35, F-26, F-33, F-48, F-43 | ☑ (**PR #31** merged → dev) | `docs/plans/fix-P2-honesty.md` |
| **P3** | Search: scope, teams, hardening | data/analytics + api + tests | — | F-44, F-45, F-47 | ◐ (VERIFY: gate green; real-DB click-through + PR BLOCKED on **F-50** DB regen) | `docs/plans/fix-P3-search.md` |
| **P4** | Transactions (dashboard roster-diff tier) | analytics + api + frontend | — | F-37 (tier 1) | ☐ | `docs/plans/fix-P4-transactions.md` |
| **P5** | Frontend: navigation & presentation fixes | frontend | P1 (data it renders) + F-24 contract | F-34, F-36, F-05, F-24, F-07, F-15, F-46, F-14, F-11, F-40, F-30, F-04, F-28, F-02, F-42 | ☐ | `docs/plans/fix-P5-frontend-fixes.md` |
| **P6** | Frontend: composition, seasonality & insight enhancements | frontend | P1, P4, P2 | F-01, F-29, F-08, F-03, F-09, F-18, F-38, F-21, F-41 | ☐ | `docs/plans/fix-P6-frontend-insights.md` |
| **UP** | Upstream / Phase-1 program & research (NOT dashboard PRs) | data (pipeline) + research | runs alongside | F-27, F-25, F-37 (tier 2), F-06, F-49, F-50 | ☐ | per-program handoffs in `docs/handoffs/` |

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
- [P2, 2026-06-04] **BUILD: one shared pre-2016 affordance** (`PRE2016_GAP_NOTE` in `web/src/design-system/index.tsx`) now drives the matchups/team/stats banners and the season-selector label, so the copy reads identically (F-33). The `DataGap` `season_unscored` label was reworded to "Per-player scoring not reconstructed (pre-2016)" and a new `pre2016_unscored_rostered` reason added for F-26. → P5/P6 should reuse `PRE2016_GAP_NOTE`, not re-author the copy.
- [P2, 2026-06-04] **BUILD: F-26 unscored-era detection is frontend-derived** — a player is "unscored-era-only rostered" when `last_rostered_season < min(scored season year)`, where the min scored year comes from the backend's per-season `is_scored` flag (no hardcoded 2016, no metric math). → if a later pass adds a backend `era` field, the player-detail derivation can read it instead.
- [P2, 2026-06-04] **BUILD: F-48 is presence-vs-accuracy, no contract change** — `dst_scoring_complete` stays `true` (it asserts scored-DEF *presence*); the known nflverse yards/sacks value-accuracy gap is documented dev-facing in `coverage.py` + `docs/03`. → the real DST value fix is upstream (danger-zone), not a dashboard finding.
- [P3, 2026-06-05] **PLAN:** Phase-1 `search_players` uses `name.ilike("%q%")`, so `%`/`_` act as SQL LIKE wildcards; P3 neutralises this dashboard-side by re-filtering candidates through `_match_rank` (plain casefold, no `re`) instead of touching Phase-1 (read-only boundary). The existing `rank=None→1` coercion (keeps non-matching players) is dropped as part of this. → no Phase-1 change; correctness + F-47 hardening, no contract change.
- [P3, 2026-06-05] **PLAN:** F-45 fantasy-team search needs a distinctive fixture `team_name` (today `team_name = f"{display_name} {year}"`, a mere owner-name alias); conftest gains one "Northvale Scumbags"-style team. Fantasy-team hits resolve to `type="team"` → `/managers/{owner_id}` (no team page). The old `test_teams_are_never_emitted` assertion is replaced. → preserve P1's 2015 bracket + 2017 wk4 cap rows when editing conftest.
- [P3, 2026-06-05] **PLAN:** F-46 (dropdown scroll) and any `dangerouslySetInnerHTML` on the search dropdown are **frontend → P5**, not P3; P3's F-47 XSS coverage is a backend "hostile string returned as inert data" test only. → keeps P3 single-layer (data/api/tests).
- [P3, 2026-06-05] **BUILD:** the fixture's `jjet` is deliberately the *never-rostered* scope example (`test_player_index_scopes_to_league_relevance`), so F-44's `league_relevant=True` filter **excludes** it. The plan's F-45 positive NFL-team cases (planned on jjet=MIN) were re-pointed at **cmc=SF** (genuinely rostered); jjet=MIN now serves the league-scope *exclusion* case instead. `test_player_substring_match` (was `"jeff"`→jjet) was likewise re-pointed at cmc, since F-44 makes jjet unsearchable by name. → no scope change; the plan's intent holds with a league-relevant subject.
- [P3, 2026-06-05] **BUILD:** F-47 frontend XSS — grep confirms **no `dangerouslySetInnerHTML`** anywhere in `web/src/`; React escapes search labels by default. → no P5 item needed for search-dropdown XSS; backend inert-data test is sufficient.
- [P3, 2026-06-05] **BUILD:** the fixture's owner-alias team names (`"{owner} {year}"`) now emit redundant `type="team"` hits alongside the owner hit (e.g. "Maverick" → owner + "Maverick 2015/2016"). Harmless (both deep-link to the same manager) and a fixture artifact — real `team_name`s are distinctive. Dedup is per distinct name → most-recent owner, per the plan. → if P5/P6 finds the redundancy noisy in the real DB, suppress team hits whose name equals an owner's display-name there (frontend/presentation), not here.
- [P3, 2026-06-05] **VERIFY: real-DB 500, app-wide → routed to UP as F-50 (BLOCKER).** The real-DB click-through hit `OperationalError: no such column: teams.team_avatar_asset_id` (HTTP 500) on **every** full-entity `select(Team)`, not just search: ff-pipeline advanced to **1.2.0** (added `teams.team_avatar_asset_id`/`owner_avatar_asset_id`) but the on-disk `fantasy.db` predates those columns. Confirmed 500 on `/v1/search`, `/v1/owners`, `/v1/owners/{id}`, `/v1/seasons` (reads at `search.py:100`, `owners.py:94`, `standings.py:67/152`). Fixture tests can't catch it — the fixture DB is built from the live 1.2.0 ORM, so every column is present; only the real-DB run surfaces it. **Decision (user):** fix upstream — regenerate `fantasy.db` with the 1.2.0 pipeline in danger-zone; **dashboard code unchanged** (a VERIFY-time `select(Team)`→explicit-columns narrowing of `search.py` was reverted for uniformity). → new finding **F-50 assigned to UP**; P3's search code is verified correct (fixture suite green + real-DB behavior confirmed via a temporary column workaround), but the **real-DB click-through and the P3 PR are BLOCKED until the DB is regenerated**. No dashboard change is needed when the regen lands.
- [P1, 2026-06-04] Git base: the roadmap + 48-findings doc + fix-pass skill are in **open PR #29** (→ dev), not yet on `dev`. The fix-P1 PLAN doc is committed onto `feature/in-browser-review-findings` (rides into dev via #29). **#29 must merge before `/fix-pass P1 build`** so the BUILD branch cuts cleanly from an up-to-date `dev`. → sequencing dependency for every fix-pass.

## Done when (the whole program)

- Every pass P1–P6 is ☑ merged to `dev`, its findings resolved, its plan doc on disk.
- The gap-validation harness (F-43) is green and asserts the coverage truths.
- `PROGRESS.md` reflects the post-review state; `docs/09_ROADMAP.md` unaffected (this is a separate
  program); the review doc's findings each show their resolving PR.
- UP items are tracked as Phase-1 programs with their own handoffs; this roadmap notes which
  dashboard findings each UP win retires.
