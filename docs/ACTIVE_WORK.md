# ACTIVE_WORK.md — dz-dashboard (active aggregate)

The consolidated, **non-archived** record of everything not yet done: remaining tasks,
in-progress work, blockers, open decisions, the upstream program, and deferred enhancements.
This is the **forward-looking** companion to `docs/archive/COMPLETED_WORK.md` (finished work).

Read order at session start stays: `PROGRESS.md` → the relevant `docs/09_ROADMAP.md` row /
`docs/plans/REVIEW_FIXES_ROADMAP.md` → this file for the open scope.

Status key: ☐ todo · ◐ in progress · ⊘ blocked (needs an input/decision) · ⤴ upstream (out of
this repo, in `../danger-zone` / ff-pipeline).

---

## 0. At-a-glance — what is actually open

The dashboard application is functionally complete (all P0–**P12** milestones and all P1–P6
review fix-passes are merged — see the archive). The only un-merged dashboard work is the
**rivalries-insights** branch (rivalry insight bands; awaiting PR to `dev`).

> **Forward execution plan:** `docs/plans/COMPLETION_ROADMAP.md` sequences all remaining work into
> handoff-ready sessions **S1–S8** (S1 baseline-green+conferences → S2 ship rivalries-insights →
> UP program S3–S7 → S8 league-history expansion). The priority list below maps onto those.

The remaining work is, in priority order:

1. **⚠ Baseline tech-debt — backend gate is red (broad, data-service level).** §6.1. Conferences
   ORM model drift (live route + bracket dependency) and stale matchups tests have been carried as
   "pre-existing, unrelated" across many PRs and keep `mypy`/`ruff`/`pytest` from passing on the
   `dev` baseline. **Escalated** — fix before/with the rivalries-insights PR. ☐
2. **The UP (upstream / danger-zone) program** — Phase-1 data/research, not dashboard PRs. ⤴
   (**F-54** season-correct player NFL team is now ☑ — merged PR #51; see §2.)
3. **League-history expansion** once upstream identity/rules data exists. ☐
4. **Deferred product decisions** (theme toggle, avatars, exports, etc.) — reversible defaults,
   all settled at their defaults (§4). ☑/☐
5. **Housekeeping** (`pyproject.toml` fallback-tag bump). ☑ done — see §6.2.

---

## 1. In-progress / immediate — feature branches ☑/◐

**Merged since the last consolidation:** season-correct NFL team (F-54, PR #51), box-score
roster layout + injury reports / P12 (PRs #52/#53), commissioner history, the playoffs/bracket
visualization and its championship/consolation split (PRs #55/#60), the seasons/rules redesign +
setting-gap resolution (PRs #54/#59), and the standings-500 fix (PR #57). Earlier: league-history,
season-aware team names, player zero-week fix, records champion name, team avatars (PRs #47–#50).
All are on `dev` and promoted to `main` via PRs #56/#58.

**Currently open (one branch):** `feature/rivalries-insights` — five league-wide rivalry insight
bands + `GET /v1/rivalries/insights`. Committed to the branch and pushed to origin; **PR to `dev`
not yet opened.** Before it merges, clear the §6.1 baseline gate breakage it inherits. Plan:
`docs/plans/rivalries-insights.md`.

- **After rivalries-insights, dashboard work is gated on the UP program** (§2): each upstream
  data fix retires a finding behind the read-only boundary, then the dashboard consumes it. The
  only other open buildable dashboard work is league-history expansion (§3), which also waits on
  upstream identity/rules data.

---

## 2. The UP program — upstream / danger-zone (Phase-1 data & research) ⤴

These are **not dashboard PRs.** They live in `../danger-zone` (ff-pipeline). Each, when it
lands, retires one or more dashboard findings without a dashboard code change (read-only
boundary). Detailed log: `docs/plans/REVIEW_FIXES_ROADMAP.md`; per-program handoff:
`docs/handoffs/players-audit-danger-zone.md`. Status reflects the 2026-06-07 read-only spot check.

### F-06 — Ownership-succession history ☐ ⊘ (needs a source)
A human/source ledger of which owner held which team across which seasons. There are 12
persistent teams but >12 owners over time; owner ≠ team and tenures vary. **Blocked on a
source/table.** Should precede any schema or manager-record reinterpretation.
(See memory `owner-vs-team-identity`.)

### F-25 — Residual player-identity cleanup ◐ ⤴ (improved, not closed)
Rerun the player-audit queries in `docs/handoffs/players-audit-danger-zone.md` (use the
status-update counts, not the original counts), then fix or document the residuals upstream.
Current real-DB residual (3048 players):
- D1 `last_season IS NULL` = 277 (was 100%); largely improved, still open.
- D2 league-rostered `rookie_year IS NULL` = 38; open.
- D4 never-rostered / never-scored "ghost" players = 400; scope-policy decision still open.
- D5 duplicate same-player/season/week roster rows = **0** → effectively resolved.
- D3 `is_active` semantics + stale `nfl_team` — needs a documented, stable definition.
- Coordinated API addition: expose `last_season` on `PlayerOut` once D1 is fully populated
  (additive; run dashboard `gen:api` drift check in the same cycle).
Remaining nulls/ghosts must be either fixed or documented as **true source gaps**.
(See memory `player-stub-duplicates`.)

### F-27 — Trust check on reconstructed pre-2016 scoring ◐ ⤴ (data landed; validation open)
The data half is ☑ (F-51: `player_stats_scored` spans 2010–2025). **Still open:** sanity-check
representative weeks, outliers, and season totals for 2010–2015 against source NFL.com / team
totals before treating every reconstructed score as authoritative.

### F-37 tier 2 — Exact transactions & FAAB ◐ ⤴ (partly landed)
Upstream now has dated, typed transaction rows (add/drop/waiver/free-agent/trade/draft/lineup),
and the dashboard renders the derived roster-diff tier. **Open:** the dashboard has not yet
consumed exact transaction dates/types as a richer tier, and **no FAAB bid rows were present** in
the spot check. Determine whether historical FAAB bid amounts exist anywhere; if absent, document
`faab_bid:null` as a true source gap. The waiver standard-order → FAAB switch point is still
unresolved.

### F-49 — Playoff / consolation metadata ☐ ⤴
`Matchup.is_consolation` is `0` for all playoff rows and `is_playoff` is set on every
post-season game, so all 12 teams look like they advanced each season. The dashboard therefore
returns `made_playoffs = None` unless a season's bracket is a proper subset of the league
(a few older seasons qualify), and the `/bracket` view stays caveated. **Fix source-derived
`is_consolation` / playoff-team metadata in ff-pipeline** (prefer fixing source flags over
dashboard inference); `made_playoffs` then resolves with no contract change.

### F-54 — Season-correct player NFL team ☑ (MERGED, PR #51 — dashboard + upstream)
Upstream persisted the per-week NFL team (`player_stats_raw.nfl_team`, nflverse's current
franchise code) and shipped the season-correct read helpers
`queries.player_season_teams(session, player_ids, season_year)` (batched) and
`queries.player_nfl_team(...)`, which fold the stored code to the season-era one via
`historical_team_code` (a 2015 Raider reads "OAK", not "LV"). The dashboard now routes its two
season-scoped reads — `analytics/stats.py:season_totals` (batched, one query per leaderboard
page) and `analytics/teams.py:team_roster` — through `player_season_teams`, falling back to the
`players.nfl_team` snapshot when no per-week team is stored (mirrors `period_team_name()`). No
API response **shape** change; only the value becomes season-correct. Known-answer test:
`tests/test_fixp1_stats.py::test_season_correct_nfl_team_overrides_current_snapshot`. Real-DB
spot check (2026-06-10): 2015 leaderboard renders SD/OAK/STL (Rivers, Carr, Gurley) instead of
their current snapshots. Handoff (now closed):
`docs/handoffs/season-correct-nfl-team-danger-zone.md`.

### Resolved-upstream (no longer open) — for reference
F-50, F-51, F-52, F-53 are all ☑ via the regen — see `docs/archive/COMPLETED_WORK.md` §5.
F-54 ☑ (see above) — upstream persisted the per-week team and the dashboard consumes it.

---

## 3. League-history expansion (next product slice) ☐

The league-history slice is landed (archive §3). Its next expansion should **consume
upstream/manual identity and rules data when available**:
- durable human manager overrides (depends on F-06);
- roster-slot settings; full scoring-rule tables; playoff-format metadata (depends on F-49);
- verified scoring-mismatch classification (depends on F-27).

Per-season config ledger is needed: scoring rules, season length (1–13 → 1–14), waiver → FAAB,
and ownership all changed over time. Switch-years are TBD. (See memories
`league-settings-ledger`, `owner-vs-team-identity`.)

---

## 4. Open product decisions — deferred at defaults (reversible) ☐

From `docs/10_OPEN_QUESTIONS.md`. All shipped at a sensible default and remain reversible.

| # | Decision | As-built default | Open? |
|---|----------|------------------|-------|
| Q8 | Keep-alive / run model | one-command (`make serve`); auto-start options provided but not installed | settled at default |
| Q9 | Caching aggressiveness | in-process only, keyed on `latest_pipeline_run_id`; no materialized table | open only if first-hit latency bites |
| Q10 | Theme toggle | dark-only; `tokens.css` ready for a light set but no `[data-theme="light"]` / UI toggle | **settled 2026-06-08: keep dark-only** |
| Q11 | Avatars / logos / photos | team logos streamed from the DB asset store (`GET /v1/teams/{id}/avatar`), monogram fallback; owner photos a true source gap | **done 2026-06-08** (`docs/archive/deferred-product-decisions.md`) |
| Q12 | Mobile priority | laptop-first responsive | **settled 2026-06-08: keep laptop-first** |
| Q13 | Exports / sharing | none | **settled 2026-06-08: no exports** |

---

## 5. Open items / deviations & known non-blockers

- **Phantom week-1-only teams (identity artifact).** 1–2 phantom week-1-only teams per season
  with duplicate/garbled names (e.g. "JFCFPWCPGAWWLTDOSGT", "Rev Russell's Sunday Service"),
  ~2 matchups each, present 2010–2018 and absent 2019/2023/2025. **Separate** from the repaired
  F-53 roster-churn corruption; belongs with the owner/team-identity research (F-06). Worth a new
  finding if it surfaces in the UI.
- **League relevance = ever-rostered only** (not "ever scored"): the pipeline scores the whole
  NFL, so "scored" is not a league-relevance signal. Keep filters on roster presence.
- **F-49 `made_playoffs = None`** where a bracket can't be inferred honestly — intentional until
  upstream metadata lands (see §2 F-49).

---

## 6. Housekeeping & baseline tech-debt

### 6.1 ⚠ Backend gate red on the `dev` baseline — ESCALATED ☐

Carried across multiple PRs as "pre-existing, unrelated, left untouched." Escalated here because
it sits in **broad, long-lasting data-service code** and blocks a green backend gate. Confirmed
current 2026-06-14 (`uv run mypy src/ff_dashboard`, `ruff check`, `pytest tests/test_p5_matchups_unit.py`):

- **Conferences module written against non-existent ORM models (highest priority).**
  `src/ff_dashboard/analytics/conferences.py` imports `SeasonConference` and reads
  `Team.conference_id` — **neither exists in the Phase-1 ORM** (verified 2026-06-14: the import
  raises `ImportError`; `hasattr(Team,"conference_id") == False`; not in `Team.__table__.columns`).
  The `try/except` import-guard then sets `_CONFERENCE_MODELS_AVAILABLE = False`, so **the
  conferences feature is silently dead for the 2010–2019 conference era** — every season wrongly
  returns `no_conferences_this_season`, and `conference_map()` (consumed by `analytics/bracket.py`)
  returns `{}`. Surfaces as **3 mypy errors** (lines 37/40/84) + 1 ruff import-sort error. The data
  is reachable — `standings.py` (lines ~78–96) already reads the same `teams` / `season_conferences`
  tables via raw SQL and works (the same approach PR #57 used for the standings-500 fix).
  **Fix path (dashboard-side, preferred):** rewrite `conferences.py`'s two query sites to the raw
  SQL `standings.py` uses — this clears the gate **and** repairs the dead feature, with no upstream
  dependency. **Full handoff: S1 in `docs/plans/COMPLETION_ROADMAP.md`.**
- **Stale matchups unit tests.** `tests/test_p5_matchups_unit.py` asserts a `lineup_score_gap` /
  `gap_delta` box-score field that **no longer exists in source** (`has_long_td_score_gap` was
  removed) → **2 pytest failures** (`test_box_score_gap_delta_is_total_minus_starters`,
  `test_box_lineup_score_gap_is_false_without_bonus_rules`). Update or delete the assertions to
  match the shipped box output.
- **Minor:** 1 ruff ambiguous-unicode error in `analytics/league_history.py`.

### 6.2 `pyproject.toml` git-fallback tag ☑

- **`pyproject.toml` git-fallback tag.** ☑ Bumped the documented git-source fallback example from
  `v1.0.0` to `v1.2.0` (the earliest danger-zone tag carrying the team/owner avatar columns the
  live DB needs; danger-zone is now at `v1.2.0` / `1.2.1` working tree). Updated the matching
  prose in `docs/PHASE2_RUNBOOK.md` and `docs/00_SEAM.md`. The active source stays the editable
  path to `../danger-zone`; this only touches the commented CI/reproducible fallback. Bump again
  whenever the live DB is regenerated from a newer pipeline release.

---

## 7. Questions to revisit at end of Phase 2 (before Phase 3)

From `docs/10_OPEN_QUESTIONS.md` — input-gathering, not blocking work:

- Which views did you actually use? Which planned ones went untouched?
- Did any analytics metric need a definition change once seen on real data?
- Is the in-process cache adequate, or do the big rollups want precomputation?
- Did the BFF stay a thin analytics layer, or is it creeping toward logic Phase 3 should own?
- What new views did you wish for while using it (the most valuable Phase-3 scope input)?

---

## Source docs feeding this aggregate

- `PROGRESS.md` — current-state snapshot (Current state / Next / Files that matter now)
- `docs/plans/REVIEW_FIXES_ROADMAP.md` — detailed append-only build log + UP tracking
- `docs/10_OPEN_QUESTIONS.md` — deferred questions & build-surfaced issues (N5)
- `docs/handoffs/players-audit-danger-zone.md` — the F-25 upstream handoff (D1–D5)
- `docs/handoffs/review-fix-pass.template.md` — manual fix-pass workflow fallback
- `docs/reviews/2026-06-in-browser-review.md` — the 48-finding review (F-01–F-48)
