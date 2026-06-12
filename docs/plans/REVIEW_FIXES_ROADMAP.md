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
| Season-length switch year(s): regular 1–13 → 1–14; playoffs/championship week shift | P1 (F-32) | ⊘ optional / unresolved | Dashboard derives from DB columns until the exact switch year is supplied; `_CONFIRMED` remains empty. |
| Waiver standard-order → **FAAB** switch point | UP (F-37) | ◐ partly retired | `danger-zone` now has dated transaction rows with waiver/free-agent/trade/drop/draft/lineup types, and dz-dashboard consumes them on the team page; no FAAB bid rows were present in the 2026-06-07 spot check. |
| Ownership-succession history (which owner held which team, which seasons) | UP (F-06) | ☐ pending | Still needs a source / table. |
| Pre-2016 scoring reconstruction: go / sequencing | UP (F-27) | ☑ data landed; ◐ trust check open | `player_stats_scored` spans 2010–2025; retain the F-27 sanity-check before treating every reconstructed score as final. |

## Status

Key: ☐ todo · ◐ in progress · ☑ merged · ⊘ blocked (needs an input above)

| Pass | Title | Primary layer | Depends on | Findings | Status | Plan doc |
|------|-------|---------------|------------|----------|--------|----------|
| **P1** | Analytics correctness, scoping & enrichment (incl. season-structure model) | analytics + api | — (season model config-driven) | F-32, F-22, F-31, F-10, F-12, F-23, F-17, F-13 | ☑ (**PR #30** merged → dev) | `docs/archive/fix-P1-analytics.md` |
| **P2** | Data honesty & affordance precision (+ gap-validation harness) | gap-affordance + tests | soft: P1 (week semantics) | F-16, F-35, F-26, F-33, F-48, F-43; post-regen redo for F-51 | ☑ redo merged (PR #34) | `docs/archive/fix-P2-honesty.md`; redo: `docs/archive/fix-P2-post-regen-redo.md` |
| **P3** | Search: scope, teams, hardening | data/analytics + api + tests | — | F-44, F-45, F-47 | ☑ PR #32 (real-DB click-through done post-regen; F-50 resolved) | `docs/archive/fix-P3-search.md` |
| **P4** | Transactions (dashboard roster-diff tier) | analytics + api + frontend | — | F-37 (tier 1) | ☑ PR #35 merged (F-53 fixed upstream; real-DB verified) | `docs/archive/fix-P4-transactions.md` |
| **P5** | Frontend: navigation & presentation fixes | frontend | P1 (data it renders) + F-24 contract | F-34, F-36, F-05, F-24, F-07, F-15, F-46, F-14, F-11, F-40, F-30, F-04, F-28, F-02, F-42 | ☑ PR #38 merged | `docs/archive/fix-P5-frontend-fixes.md` |
| **P6** | Frontend: composition, seasonality & insight enhancements | frontend | P1, P4, P2 | F-01, F-29, F-08, F-03, F-09, F-18, F-38, F-21, F-41 | ☑ PR #40 merged (full gate green; real-DB verified; F-52 closed) | `docs/archive/fix-P6-frontend-insights.md` |
| **UP** | Upstream / Phase-1 program & research (NOT dashboard PRs) | data (pipeline) + research | runs alongside | F-27 (data half ✅ landed → F-51; sanity-check open), F-25 residual, F-37 tier 2 ◐ (dated typed rows exist and dashboard consumes them; FAAB rows absent), F-06, F-49, ~~F-50~~ ✅ regen, ~~F-52~~ ✅ regen (confirmed P6 VERIFY), ~~F-53~~ ✅ regen (wk1 fixed) | ◐ | per-program handoffs in `docs/handoffs/` |

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
- **P4** — review doc § "P4 — Transactions". PR #35 shipped the roster-diff derivation; a later
  local pass now consumes exact upstream transaction rows. FAAB availability remains UP/nullable.
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
- [P3, 2026-06-06] **VERIFY: DB regenerated → P3 unblocked, MERGED-pending PR #32; two new findings surfaced.** The new `fantasy.db` carries the 1.2.0 columns (F-50 ✅ resolved); the search click-through completed on the real DB (F-44/45/47 all confirmed). The regen also brought **significant new data**: (1) **F-51** — pre-2016 per-player scoring is now reconstructed (`player_stats_scored` spans 2010–2025, `is_scored:true` for all 2010–2025), which *inverts* the merged P2 honesty work — the live pre-2016 "no player scoring" banners/DataGaps now over-claim a filled gap, and P1's F-22 scored-window (2016–2025) is stale; needs a re-verify pass. (2) **F-52** — every `seasons.status` is `in_progress` (all 17 rows, incl. completed 2010–2025); only 2026 should be live → UP/pipeline artifact. → P3 ships clean (search is independent of `is_scored`/`status`); F-51/F-52 logged for follow-up passes.
- [P3, 2026-06-05] **VERIFY: real-DB 500, app-wide → routed to UP as F-50 (BLOCKER).** The real-DB click-through hit `OperationalError: no such column: teams.team_avatar_asset_id` (HTTP 500) on **every** full-entity `select(Team)`, not just search: ff-pipeline advanced to **1.2.0** (added `teams.team_avatar_asset_id`/`owner_avatar_asset_id`) but the on-disk `fantasy.db` predates those columns. Confirmed 500 on `/v1/search`, `/v1/owners`, `/v1/owners/{id}`, `/v1/seasons` (reads at `search.py:100`, `owners.py:94`, `standings.py:67/152`). Fixture tests can't catch it — the fixture DB is built from the live 1.2.0 ORM, so every column is present; only the real-DB run surfaces it. **Decision (user):** fix upstream — regenerate `fantasy.db` with the 1.2.0 pipeline in danger-zone; **dashboard code unchanged** (a VERIFY-time `select(Team)`→explicit-columns narrowing of `search.py` was reverted for uniformity). → new finding **F-50 assigned to UP**; P3's search code is verified correct (fixture suite green + real-DB behavior confirmed via a temporary column workaround), but the **real-DB click-through and the P3 PR are BLOCKED until the DB is regenerated**. No dashboard change is needed when the regen lands.
- [P1, 2026-06-04] Git base: the roadmap + 48-findings doc + fix-pass skill are in **open PR #29** (→ dev), not yet on `dev`. The fix-P1 PLAN doc is committed onto `feature/in-browser-review-findings` (rides into dev via #29). **#29 must merge before `/fix-pass P1 build`** so the BUILD branch cuts cleanly from an up-to-date `dev`. → sequencing dependency for every fix-pass.
- [P4, 2026-06-06] **PLAN:** the review's signature `derive_transactions(team_id, season)` is renamed **`derive_roster_moves(session, team_id)`** to avoid colliding with the existing `team_transactions` (Phase-1 `Transaction` table, draft-only on the real DB) and to name it as a *derived roster diff*. P4 is **additive** — a new `/v1/teams/{team_id}/roster-moves` endpoint + `RosterMove`/`TeamRosterMoves` schema; the existing transactions endpoint/shape is untouched, so the draft space stays and the in-season space is new. `gen:api` will show the new path (expected, not drift on existing). Moves are **not gated on `is_scored`** (roster snapshots predate the scoring reconstruction). A season with <2 roster snapshots → `available:false` + new `DataGap` reason `roster_history_unavailable` (never zeros). → no Phase-1 change; one fixture edit (2-week roster scenario on mav 2016) that must preserve P1/P3 known answers.
- [P4, 2026-06-06] **BUILD:** implemented `analytics/transactions.py:derive_roster_moves` (stint-model diff over `team_rosters`), additive `/v1/teams/{team_id}/roster-moves` + `RosterMove`/`TeamRosterMoves` schema, frontend `RosterMovesCard` + `roster_history_unavailable` `DataGap`; relabelled the existing transactions space "Draft" (draft-only on real DB). `gen:api` drift = the new path only (+81 lines, 0 deletions). Fixture gained mav-2016 wk2 rows (cmc retain / dst drop / "Waiver Wendell" add) and a mav-2015 unscored 2-week scenario ("Vintage Vince" retain). **One prior known-answer updated, legitimately:** cmc's 2016 ownership span is now weeks 1–2 (was a single week) since cmc gained a wk2 roster row — `test_ownership_timeline_collapses_into_spans` re-pointed to `(2016, 1, 2)` (still demonstrates contiguous-week collapse). 211 backend + 8 team-page vitest green. → no contract change beyond the additive path; VERIFY runs the full gate + real-DB click-through.
- [P4, 2026-06-06] **VERIFY: full gate GREEN but real-DB click-through surfaced a blocker → new finding F-53.** Backend 211 pytest / ruff / mypy / write-safety all clean; frontend `gen:api` no drift / typecheck / 132 vitest clean. The real-DB click-through on `/v1/teams/{id}/roster-moves` revealed that `team_rosters` **week 1 is a corrupt/placeholder snapshot in every season 2010–2025** (disjoint from wk0 + wk2, 0–7/17 overlap; 2010 teams' wk1 lists modern players like Brock Purdy). P4's `derive_roster_moves` is the first reader to diff *all* weeks, so it faithfully renders the corrupt wk1 as fabricated churn (e.g. 68 adds + 67 drops at wk1) — an honesty violation if shipped. The existing single-week roster view hides this. **P4 code is correct on the input; the defect is upstream data.** → **P4's PR is BLOCKED until F-53 is fixed in danger-zone** (no dashboard workaround — read-only boundary; mirrors how F-50 blocked P3 until the regen). Once wk1 is consistent with its neighbours, P4 derives correctly with no code change. F-53 assigned to UP.
- [P4/F-53, 2026-06-06] **F-53 FIXED in danger-zone (regen) → P4 UNBLOCKED.** Lightweight real-DB recheck on `../danger-zone/data/fantasy.db`: for the 12 real franchises, wk1∩wk2 player-id overlap is now **0.71–0.88** across every season 2010–2025 (was 0–7/17), and wk1 holds period-correct players (2010 wk1 → Dez Bryant, not Brock Purdy/Bucky Irving). The fabricated "68 adds + 67 drops at wk1" churn is gone. **No dashboard code change** — as predicted, P4's derivation is correct once the input is clean. **Real-DB verification PASSED (2026-06-06):** `/v1/teams/{id}/roster-moves` via the app — team 184/2024 (the original 68-adds/67-drops case) now returns wk1 2 adds/0 drops; 2010 team 13 → wk1 5/5, period-correct players; all-season totals at normal waiver levels. Residual (a separate identity artifact, *not* this churn corruption, not blocking): 1–2 phantom **week-1-only** teams per season with duplicate/garbled names ("JFCFPWCPGAWWLTDOSGT", "Rev Russell's Sunday Service"), ~2 matchups each, present 2010–2018 and absent 2019/2023/2025 — belongs with the owner/team-identity research, worth a follow-up finding if it surfaces in the UI.
- [P4, 2026-06-06] **MERGED:** PR #35 (`feature/fix-P4-transactions`) merged to `dev`; F-37 tier 1 is complete. Later local work consumes exact dated/type transaction rows from upstream; FAAB rows remain absent in the current spot check.
- [P5, 2026-06-06] **PLAN:** wrote `docs/plans/fix-P5-frontend-fixes.md`. BUILD should start with F-24 contract cleanup, then shared controls/charts, then navigation fixes, then page-local presentation polish.
- [P5, 2026-06-06] **BUILD:** implemented F-24 player-index contract cleanup, shared `WeekStepper`/search/timeline readability fixes, team/box-score/manager navigation fixes, manager sort/rivalry label polish, signed matchup margins, 12-column snake draft board, stats season-total default, standings finish column, and compact player ownership cards. Focused backend/frontend slices and frontend typecheck are green.
- [P5, 2026-06-06] **VERIFY:** full gate green (211 pytest, ruff, mypy, generated-client drift clean, typecheck, 139 vitest; `npm run lint` is N/A because no script). Write-safety grep only hits the existing read-only guard docstring in `engine.py`. Real-DB browser click-through passed for players contract cleanup, manager sort/latest roster, team season navigation and schedule fallback, matchup week select and signed margins, scored box score, draft 12-column snake grid, stats season-total default, standings/power timelines, and scrollable search. → PR #38.
- [P5, 2026-06-06] **MERGED:** PR #38 (`feature/fix-P5-build`) merged to `dev`; P5 is complete.
- [F-51, 2026-06-06] **NEW PASS (off the original P1–P6 plan): F-51 resolved on `feature/fix-F51-current-season-scoring`.** The `fantasy.db` regen reconstructed pre-2016 player scoring (`player_stats_scored` 2010–2025), inverting P2's hardcoded "pre-2016 unscored" *copy* into an over-claim; the only unscored season is now the current in-progress one. Fix is **frontend copy + a generalized player-detail predicate, no gating change** (all gates were already data-driven on `is_scored`) + live-doc updates. Verified on the real DB (built SPA). → **Branch-ordering:** the F-51 *finding* entry lives on **PR #32** (fix-P3); this PR carries the *resolution*. Recommend merging **PR #32 first**; if not, expect a trivial duplicate-`F-51` conflict in the review doc/roadmap to resolve by hand. F-52 (`seasons.status` all `in_progress`) stays UP (danger-zone).
- [P2-redo, 2026-06-06] **PLAN:** post-regen P2 redo plan written at `docs/archive/fix-P2-post-regen-redo.md`. The historical P2 plan is retained for PR #31, but BUILD should now follow the redo plan: update stale coverage harness assumptions, confirm records/player windows derive from `is_scored`, and verify 2010/2015/2025/current-season behavior on the real DB. → no DB writes; no API shape change expected.
- [P2-redo, 2026-06-06] **BUILD:** F-43 harness no longer asserts "player scoring absent pre-2016"; it discovers scored seasons from rows and keeps 2015 only as a synthetic generic unscored gap in the fixture. Records tests now assert player windows against `KNOWN["seasons_scored"]`; stale analytics comments were reframed to generic coverage gaps. Scoped backend/frontend checks green. → VERIFY still needs the full gate and real-DB click-through.
- [P2-redo, 2026-06-06] **VERIFY:** full gate green (206 pytest, ruff, mypy, contract no drift, typecheck, 129 vitest; `npm run lint` is N/A because no script). Real DB confirms 2010/2015/2025 scored, 2026 unscored, records/meta scored window 2010–2025, 2010/2015/2025 box scores available, player 8299/Arian Foster has 2010 scoring and a 2026 `season_unscored` gap. Built SPA single-origin routes served. → P2 redo is verified; F-52 remains UP.
- [P6, 2026-06-06] **PLAN:** the requested home playoff bracket is not planned as frontend
  inference because `/v1/seasons/{season_id}/bracket` is still unbuilt/caveated and F-49 leaves
  bracket metadata partly upstream. P6 BUILD should show proven last-season finish/championship
  context on Home, and use `DataGap` for unavailable bracket/activity data. → avoids inventing
  bracket structure while still satisfying the season-aware home re-curation.
- [P6, 2026-06-07] **VERIFY:** full gate green (213 pytest, ruff, mypy, gen:api no-drift,
  typecheck, 139 vitest, SPA production build; `npm run lint` is N/A — no script). Ran `ruff format`
  on 3 P6 analytics files (formatting only). Real-DB checks: the two new insight endpoints
  (`/v1/players/{id}/insights`, `/v1/seasons/{id}/standings/insights`) plus box-score, power, owners
  return honest `available`/`reason` payloads with no 500s; the built SPA serves every P6 deep link.
  PR #40 opened to `dev`. → **F-52 RESOLVED upstream**, confirmed here: real DB now reports
  `status:completed` for 2010–2025 and `in_progress` only for 2026, so the season-phase helper's
  decision to derive phase from data (not `seasons.status`) is validated; closing F-52 in the review
  doc. No dashboard change needed.
- [P6, 2026-06-07] **MERGED:** PR #40 (`feature/fix-P6-frontend-insights`) merged to `dev`; P6 is
  complete. All six dashboard passes P1–P6 are now merged — the remaining open scope is the **UP**
  upstream/danger-zone program.
- [DOC-AUDIT, 2026-06-07] Reviewed plans/handoffs/roadmap/open-questions/reviews against code and
  read-only DB state. Dashboard fix-passes P1-P6 remain complete. Roadmap P11 is now complete:
  visual spec + Chromium/Linux baselines are committed, and CI runs the full Playwright suite. UP is
  partially retired: transaction rows now include dated add/drop/waiver/trade/draft/lineup types and
  dz-dashboard consumes them, but no FAAB bid rows were found. F-49 remains open
  (`is_consolation=0` for all playoff rows in the local `danger-zone` DB); F-25 is improved but
  residual (`last_season` nulls, rostered `rookie_year` nulls, and ghosts remain).

## Done when (the whole program)

- Every pass P1–P6 is ☑ merged to `dev`, its findings resolved, its plan doc on disk.
- The gap-validation harness (F-43) is green and asserts the coverage truths.
- `PROGRESS.md` reflects the post-review state; `docs/09_ROADMAP.md` unaffected (this is a separate
  program); the review doc's findings each show their resolving PR.
- UP items are tracked as Phase-1 programs with their own handoffs; this roadmap notes which
  dashboard findings each UP win retires. P11 visual-regression work is closed in
  `docs/09_ROADMAP.md` / `docs/10_OPEN_QUESTIONS.md`, not as a fix-pass.

## Remaining-work handoff (brief)

- **Bracket / F2.3 (dashboard decision):** resolved locally by the caveated `/bracket` endpoint
  and page. It exposes proven post-regular-season games only; it still does not invent playoff
  advancement or consolation structure in the SPA.
- **F-06 (ownership succession):** needs a human/source ledger of team identity vs owner tenure.
  This should precede schema or manager-record reinterpretation.
- **F-25 (player identity residual):** rerun the player-audit handoff queries, then fix or document
  the remaining `last_season`, `rookie_year`, and never-rostered/never-scored residuals upstream.
- **F-27 (trust check):** reconstructed 2010-2015 scoring exists; validate representative weeks,
  outliers, and season totals before treating it as authoritative.
- **F-37 (FAAB only):** exact transaction rows are consumed by dz-dashboard; determine whether
  historical FAAB bid amounts exist. If absent, document `faab_bid:null` as a true source gap.
- **F-49 (playoff/consolation):** populate source-derived `is_consolation` or playoff-team metadata
  in `ff-pipeline`; dashboard `made_playoffs` should then resolve without a contract change.
