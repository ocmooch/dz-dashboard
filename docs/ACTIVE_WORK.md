# ACTIVE_WORK.md — dz-dashboard (the single forward-work doc)

The consolidated, **non-archived** record of everything not yet done: remaining tasks, blockers,
open decisions, the upstream program, and deferred enhancements. This is the **forward-looking**
companion to `docs/archive/COMPLETED_WORK.md` (finished work).

Read order at session start: `PROGRESS.md` → the relevant `docs/09_ROADMAP.md` row → this file for
the open scope → the cited finding in `docs/reviews/2026-06-in-browser-review.md` if it has an
F-number.

Status key: ☐ todo · ◐ in progress · ⊘ blocked (needs an input/decision) · ⤴ upstream (out of this
repo, in `../danger-zone` / ff-pipeline) · ☑ done.

---

## 0. At-a-glance — what is actually open

The dashboard application is **functionally complete and fully merged** (all P0–P12 milestones, all
P1–P6 review fix-passes, and every post-roadmap slice — see the archive). There are **no open
feature branches.** Remaining work, in priority order:

0. **Data Integrity & Coverage program** ☑ **— COMPLETE & MERGED** (dashboard PR #77; upstream
   crosswalk landed on `../danger-zone`). The structural fix for the recurring "works here but not
   there" / wrong-`player_id` reports. All five units shipped (table kept as a record); the
   merge-sequencing step is closed — danger-zone `player_identity_cluster` and dz-dashboard #77 both
   landed.

   | Unit | Repo | What | State |
   |------|------|------|-------|
   | **A** | dz-dashboard | Coverage matrix slice: `/v1/meta/coverage`, self-explaining projection gaps, identity-split *detection* (Part B2). | ☑ merged (#77) |
   | **B** | ../danger-zone | `player_identity_links` on the live DB; seed the 18-group triage set (Mike Williams `1032↔25239`) + read-only `player_identity_cluster()` helper. Re-verified: Mike Williams is the only stranded-split; the other 17 are correct `no_link` decisions. | ☑ merged |
   | **C** | ../danger-zone | Identity-aware ingest: nflverse `gsis_id` + Sleeper projection maps resolve linked members to the canonical player before writing, so reruns attach data to `1032` instead of re-stranding. Idempotency guard `test_reingest_does_not_restrand_linked_member`. | ☑ merged |
   | **D** | dz-dashboard | Consume canonical (Part B1): box-score, team-roster, player-scoring, player-insight stat reads route through the cluster helper. `/matchups/1823` Mike Williams renders on roster id `1032`. | ☑ merged (#77) |
   | **E** | both | Sleeper returns *hollow* rows (all-zero, `projected_points=0`) for **2010–2017** — real coverage begins **2018**. Dashboard requires a *real* projection value (2017 → `projections_not_captured`, 2018+ → real); upstream `_upsert_projections` skips hollow rows + a prune deleted them (live DB 522,143 → 40,759). Box score shows one top-level note, not a per-player chip. **Pre-2018 projections do not exist at the source — unclosable, surfaced honestly.** | ☑ complete |

   Reference framing: `docs/handoffs/00-data-integrity-program.md`.
1. **Conferences feature repair** ☑ **— DONE** (PR #82). Was silently dead for 2010–2019; replaced
   by BFF-owned weekly historical division standings. §1 / §6.1.
2. **The UP (upstream / `../danger-zone`) program** — Phase-1 data/research, not dashboard PRs. §2.
3. **League-history expansion**, once upstream identity/rules data exists. §3.
4. **Deferred product decisions** — all shipped at reversible defaults. §4.
5. **Phase 3 (exploratory)** — NL "league historian" early brainstorm; kept as a local working note,
   not committed and not a milestone. A PLAN session promotes it if/when chosen.

---

## 1. Conferences feature repair (dashboard) ☑

> Detailed root cause and fix path are in §6.1. This is the only buildable *dashboard* work that is
> not gated on the upstream program; do it before anything else so the bracket/conference surfaces
> are honest for the 2010–2019 era.

Superseded by `docs/plans/bff-weekly-division-standings.md`: the live Phase 1 schema does not
actually contain the presumed conference table/column. The dashboard now owns a reviewed
2010–2019 NFL.com artifact, exact weekly in-division records, final source ranks, and the complete
historical division-table UI. 2020+ remains explicitly ungrouped.

---

## 2. The UP program — upstream / danger-zone (Phase-1 data & research) ⤴

These are **not dashboard PRs.** They live in `../danger-zone` (ff-pipeline). Each, when it lands,
retires one or more dashboard findings without a dashboard code change (read-only boundary), except
where a small additive consume-step is noted. Full finding text:
`docs/reviews/2026-06-in-browser-review.md`. Status reflects the 2026-06-07 read-only spot check.

### Inputs only you can supply (unblock these up front)

| Input | Needed by | Status |
|-------|-----------|--------|
| Season-length switch year(s): regular 1–13 → 1–14; playoff week shift | F-32 (shipped, config-driven) | ☑ dashboard derives from DB columns; exact switch year still unconfirmed |
| Waiver standard-order → **FAAB** switch point | F-37 | ✅ switch = 2021; bids landed upstream (2021–2025); team transactions log shows the bid; **weekly remaining-budget built** (`/v1/teams/{id}/faab-budget` + `FaabBudgetCard`) — see `docs/handoffs/faab-bid-capture.md` |
| Ownership-succession ledger (which owner held which team, which seasons) | F-06 | ⊘ still needs a source/table |
| Pre-2016 scoring reconstruction trust check | F-27 | ☑ data landed (2010–2025); ◐ validation open |

### F-06 — Ownership-succession history ☐ ⊘ (needs a source)
A human/source ledger of which owner held which team across which seasons. There are 12 persistent
teams but >12 owners over time; owner ≠ team and tenures vary. **Blocked on a source/table.** Should
precede any schema or manager-record reinterpretation. The commissioner-history slice is the
template to mirror (migration + seed YAML + loader + `queries.*` helper) — see
`docs/archive/commissioner-history.md`. (See memory `owner-vs-team-identity`.)

### F-25 — Residual player-identity cleanup ◐ ⤴ (improved, not closed)
Rerun the player-audit queries in `docs/handoffs/players-audit-danger-zone.md` (use the
status-update counts), then fix or document the residuals upstream. Current real-DB residual
(3048 players):
- D1 `last_season IS NULL` = 277 (was 100%); largely improved, still open.
- D2 league-rostered `rookie_year IS NULL` = 38; open.
- D4 never-rostered / never-scored "ghost" players = 400; scope-policy decision still open.
- D5 duplicate same-player/season/week roster rows = **0** → resolved.
- D3 `is_active` semantics + stale `nfl_team` — needs a documented, stable definition.
- Cross-source `player_id` splits are now explicitly tracked by the Data Integrity program.
  Dashboard detection is implemented on `feature/data-coverage-matrix-dashboard`; upstream
  crosswalk scaffolding is implemented on `feature/player-identity-crosswalk`. Still required
  upstream: curate/seed the league-relevant links (including Mike Williams 1032 ↔ 25239) and make
  ingestion consult canonical identity before creating new player stubs.
- NFL.com source-ID ownership leakage is now closed: an authenticated 2010–2025 draft/transaction
  sweep found and repaired 34 misassignments, the strict upstream audit reports zero, and the
  dashboard coverage matrix exposes any recurrence. Remaining F-25 work is metadata/scope cleanup,
  not roster/transaction identity ownership.
- Coordinated dashboard add: expose `last_season` on `PlayerOut` once D1 is fully populated
  (additive; run `gen:api` drift check in the same cycle).
(See memory `player-stub-duplicates`.)

### F-27 — Trust check on reconstructed pre-2016 scoring ◐ ⤴ (data landed; validation open)
The data half is ☑ (F-51: `player_stats_scored` spans 2010–2025). **Still open:** sanity-check
representative weeks, outliers, and season totals for 2010–2015 against source NFL.com / team totals
before treating every reconstructed score as authoritative.

### F-37 — Exact transactions & FAAB ◐ ⤴ (partly landed)
Upstream has dated, typed transaction rows (add/drop/waiver/free-agent/trade/draft/lineup) and the
dashboard renders the derived roster-diff tier. **Open:** the dashboard hasn't consumed exact
transaction dates/types as a richer tier.

**FAAB capture landed upstream + surfaced on the dashboard — MERGED (PRs #90–#93, 2026-06-21).**
Danger-zone writes `extra_data.faab_bid` on `waiver_add` legs for 2021–2025 (214/241/214/205/182
rows; pre-2021 null). Dashboard: `_faab_bid()` reads a **$0 bid as a real free claim** (394/1056 bids
are `$0`; the old `or`-chain wrongly collapsed `0`→`None`), the winning bid is an accent `"$X FAAB"`
pill in the team transactions log, and **weekly remaining-budget** shipped (`team_faab_budget()`,
`GET /v1/teams/{id}/faab-budget`, `FaabBudgetCard`): $100 base (holds exactly for 2021/2023/2024/2025)
+ mid-season per-team **credits** parsed from the budget `setting_change` events (`team_id=NULL`,
matched by name), modeled as timestamped credits so the 2022 Ice Station Zebra +$37 refund reproduces.
**Remaining open (the original F-37 scope):** the dashboard still hasn't consumed the exact
transaction dates/types as a *richer tier* beyond the acquisitions log.

### F-49 — Playoff / consolation metadata ☐ ⤴
`Matchup.is_consolation` is `0` for all playoff rows and `is_playoff` is set on every post-season
game, so all 12 teams look like they advanced each season. The dashboard returns
`made_playoffs = None` unless a season's bracket is a proper subset of the league, and the bracket
view stays caveated where it can't prove advancement. **Fix source-derived `is_consolation` /
playoff-team metadata in ff-pipeline** (prefer fixing source flags over dashboard inference);
`made_playoffs` then resolves with no contract change.

### DST team-defense yards/sacks read low ☐ ⤴ (diagnosed; pipeline fix)
Some DST box-score points under-render because nflverse team-defense stats are wrong upstream, not
because of the dashboard (which renders `PlayerStatsScored.total_points` verbatim — read-only seam).
Diagnosed 2026-06-02 on m2761 (2023 wk11): Cowboys DEF shows **24.0** vs NFL.com's **28.0**, off by
exactly 4.00. Root cause in `danger-zone/.../crawlers/nflverse/team_defense.py`:
`total_yards_allowed` is systematically inflated (crosses scoring brackets) and `def_sacks` slightly
undercounts. **Fix belongs in the pipeline:** correct the yards/sacks derivation, add the game to the
0.1-pt NFL.com scoring-verification gate, re-score + reload `data/fantasy.db` (AnalyticsCache
auto-invalidates on the new `pipeline_run_id`; no dashboard change). User chose diagnosis-only so far.
(See memory `dst-yards-sacks-pipeline-gap`. Distinct from fantasy *scoring* being end-to-end — this is
the underlying box-score stat detail.)

### Resolved-upstream (no longer open) — for reference
F-50, F-51, F-52, F-53 are ☑ via the regen, and **F-54** (season-correct player NFL team) is ☑
(merged PR #51) — see `docs/archive/COMPLETED_WORK.md` §3, §5.

---

## 3. League-history expansion (next product slice, gated) ☐

The league-history slice is landed (archive §3). Its next expansion should **consume upstream/manual
identity and rules data once it exists** — do it last, after the UP program:
- durable human manager overrides (depends on F-06);
- roster-slot settings; full scoring-rule tables; playoff-format metadata (depends on F-49);
- verified scoring-mismatch classification (depends on F-27).

A per-season **config ledger** is the missing backbone: scoring rules, season length (1–13 → 1–14),
waiver → FAAB, and ownership all changed over time; switch-years TBD. The detailed setting-change
inventory feeding this is `docs/archive/seasons-league-changes-inventory.md`. Surface it on the
Rules & Eras page with concrete change details and honest `DataGap`s where a switch-year is unknown.
(See memories `league-settings-ledger`, `owner-vs-team-identity`.)

---

## 4. Open product decisions — deferred at defaults (reversible)

From `docs/10_OPEN_QUESTIONS.md`. All shipped at a sensible default and remain reversible.

| # | Decision | As-built default | Open? |
|---|----------|------------------|-------|
| Q8 | Keep-alive / run model | one-command (`make serve`); auto-start options provided but not installed | settled at default |
| Q9 | Caching aggressiveness | in-process only, keyed on `latest_pipeline_run_id`; no materialized table | open only if first-hit latency bites |
| Q10 | Theme toggle | dark-only; `tokens.css` ready for a light set but no UI toggle | settled 2026-06-08: keep dark-only |
| Q11 | Avatars / logos / photos | team logos streamed from the DB asset store (`GET /v1/teams/{id}/avatar`), monogram fallback; owner photos a true source gap | done 2026-06-08 |
| Q12 | Mobile priority | laptop-first responsive | settled 2026-06-08: keep laptop-first |
| Q13 | Exports / sharing | none | settled 2026-06-08: no exports |

---

## 5. Open items / deviations & known non-blockers

- **Phantom week-1-only teams (identity artifact).** 1–2 phantom week-1-only teams per season with
  duplicate/garbled names (e.g. "JFCFPWCPGAWWLTDOSGT", "Rev Russell's Sunday Service"), ~2 matchups
  each, present 2010–2018 and absent 2019/2023/2025. **Separate** from the repaired F-53 roster-churn
  corruption; belongs with owner/team-identity research (F-06). Worth a new finding if it surfaces in
  the UI.
- **League relevance = ever-rostered only** (not "ever scored"): the pipeline scores the whole NFL,
  so "scored" is not a league-relevance signal. Keep filters on roster presence.
- **F-49 `made_playoffs = None`** where a bracket can't be inferred honestly — intentional until
  upstream metadata lands (§2 F-49).

---

## 6. Housekeeping & baseline tech-debt

### 6.1 Conferences feature silently dead (functional bug; gate is green) ☑

PRs #63/#64 cleared the gate-red part of this debt (stale matchups-test assertions removed;
`conferences.py` mypy/ruff silenced via `type: ignore`; e2e/format debt fixed). **But the silencing
only fixed the types — the feature is still dead at runtime** (verified 2026-06-15).

- `analytics/conferences.py` imports `SeasonConference` and reads `Team.conference_id` — **neither
  exists in the Phase-1 ORM.** The `try/except` import-guard sets `_CONFERENCE_MODELS_AVAILABLE =
  False`, so **every** call to `season_conferences()` returns `available=false,
  reason="no_conferences_this_season"`, and `conference_map()` (consumed by `analytics/bracket.py`)
  returns `{}` — **for all seasons, including 2010–2019, which genuinely had conferences.**
- The data is reachable: `analytics/standings.py` (lines ~78–96) already reads the same `teams` /
  `season_conferences` tables via raw SQL and works (the approach PR #57 used for the standings-500
  fix):
  ```python
  text("SELECT team_id, conference_id FROM teams WHERE season_id = :sid")
  text("SELECT conference_id, name FROM season_conferences WHERE season_id = :sid")
  ```
- **Consumers to keep working:** route `GET /v1/seasons/{season_id}/conferences`
  (`api/routes/seasons.py`), and `analytics/bracket.py` imports `conference_map`.
- **Fix (dashboard-side, no upstream dependency):** rewrite `conference_map()` and the inline
  team→conference query in `season_conferences()` to `text()` raw SQL like `standings.py`; drop the
  `from ff_pipeline.repository.models import SeasonConference, Team` import and the
  `_CONFERENCE_MODELS_AVAILABLE` guard (keep a defensive `try/except` around the SQL). Keep the public
  function signatures unchanged. **Add a known-answer conferences test** (none exists today — `git grep
  -l conference -- tests/` returns nothing) so the feature cannot silently die again.
- **Resolution (2026-06-17):** the proposed raw-SQL repair was based on tables/columns absent from
  the live Phase 1 schema. `feature/bff-weekly-division-standings` instead commits and validates
  NFL.com's historical regular-standings divisions/ranks, maps through `teams.team_abbrev`, and
  returns an honest mapping gap on any mismatch. The endpoint now supports weekly division records
  and the Standings page renders complete historical division tables.

### 6.2 `pyproject.toml` git-fallback tag ☑

Bumped the documented git-source fallback example from `v1.0.0` to `v1.2.0` (earliest danger-zone tag
carrying the team/owner avatar columns the live DB needs) and the matching prose in
`docs/PHASE2_RUNBOOK.md` and `docs/00_SEAM.md`. The active source stays the editable path to
`../danger-zone`. Bump again whenever the live DB is regenerated from a newer pipeline release.

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

- `PROGRESS.md` — current-state snapshot
- `docs/reviews/2026-06-in-browser-review.md` — the 48-finding review (F-01–F-48); the canonical
  finding reference the UP program still cites
- `docs/handoffs/players-audit-danger-zone.md` — the F-25 upstream handoff (D1–D5)
- `docs/archive/COMPLETED_WORK.md` — everything already shipped
