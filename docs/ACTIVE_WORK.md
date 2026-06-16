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

0. **Data Integrity & Coverage program** ◐ (cross-repo, heavy lift — the structural fix for the
   recurring "works here but not there" / wrong-`player_id` reports). **This block is the single
   cycle-state tracker** — the `docs/handoffs/*` files are reference specs, not status (their
   checkboxes were stale and lied; ignore them for state). The program was re-cut (2026-06-16) from
   3 cross-repo "workstreams" into **5 single-repo, session-sized units** because the old cut
   crossed the repo boundary, smeared status across 5 docs, and bundled reachable with unreachable
   "done when"s — which is exactly why fresh sessions kept reporting success while the symptom on
   `/matchups/1823` survived. Units, in dependency order:

   | Unit | Repo | Phase | What | State |
   |------|------|-------|------|-------|
   | **A** | dz-dashboard | VERIFY ☑ | Coverage matrix slice: `/v1/meta/coverage`, self-explaining projection gaps, identity-split *detection* (Part B2). Full gate green; click-through done on `/matchups/1823` (uncovered) + `/matchups/193` (2025 W1 covered). | ☑ verified on `feature/data-coverage-matrix-dashboard`; **pending PR → `dev`** |
   | **B** | ../danger-zone | BUILD ◐ | Put `player_identity_links` on the **live DB**, seed the 18-group triage set (start Mike Williams `1032↔25239`), expose the read-only `player_identity_cluster()` helper. Branch `feature/player-identity-crosswalk` has the table/ORM/helper coded but **not applied to the live DB, not seeded.** | ◐ early build |
   | **C** | ../danger-zone | BUILD ☐ | Identity-aware ingest: `_create_stub_players` consults the crosswalk/external-id map before minting a twin + idempotency re-ingest test. **The permanent anti-whack-a-mole piece** (without it every crawl re-mints the split). Depends on B. | ☐ todo |
   | **D** | dz-dashboard | BUILD ☐ | Consume canonical (Part B1): route matchup/player/injury joins through the cluster helper so `1823` Mike Williams renders his unioned `0.0` line (**caveat: W7 has no injury row even under the correct twin — injuries are W1–6/12–14**). Depends on B + a live-DB regen. | ☐ blocked on B |
   | **E** | ../danger-zone | BUILD ☐ (was INVESTIGATE — **resolved**) | Projections are a **crawl-coverage gap, not a source gap.** Sleeper's `api.sleeper.com/projections/nfl/{year}/{week}` (already the pipeline's source via `crawlers/sleeper/runner.py`) **serves full historical projections** — probed 2026-06-16: 2017 W7 = **9,361 rows**, 2020/2021/2023/2024 all ~9.4k. The DB only has 2024/2025/2026 W1 because the crawler was only ever *run* for those three weeks. Fix = **run the existing `run_sleeper(year, week)` over the historical (season×week) grid** (no new code; the map→score→upsert path exists), then regen the live DB. Caveat: projected→player_id goes through `sleeper_id` resolution (runner tracks `unresolved_projections`) and per-season scoring-rule application — verify both hold for older seasons. Originating `1823` Proj/Value symptom **is fixable** this way. | ☐ todo (backfill run) |

   Reference framing: `docs/handoffs/00-data-integrity-program.md`.
1. **Conferences feature repair** (dashboard, do first). The gate is green, but the feature is
   *silently dead* for the 2010–2019 conference era. §6.1.
2. **The UP (upstream / `../danger-zone`) program** — Phase-1 data/research, not dashboard PRs. §2.
3. **League-history expansion**, once upstream identity/rules data exists. §3.
4. **Deferred product decisions** — all shipped at reversible defaults. §4.

---

## 1. Conferences feature repair (dashboard · do first) ☐

> Detailed root cause and fix path are in §6.1. This is the only buildable *dashboard* work that is
> not gated on the upstream program; do it before anything else so the bracket/conference surfaces
> are honest for the 2010–2019 era.

Cut a `feature/*` branch from `dev`, rewrite the two query sites in `analytics/conferences.py` to
the raw-SQL pattern `analytics/standings.py` already uses, add a known-answer conferences test
(none exists today, which is why the feature rotted unnoticed), and verify a 2010–2019 season's
`GET /v1/seasons/{id}/conferences` returns real divisions while a 2020+ season still returns
`available=false`.

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
| Waiver standard-order → **FAAB** switch point | F-37 | ◐ dated transaction rows exist + consumed; no FAAB bid rows found |
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
transaction dates/types as a richer tier, and **no FAAB bid rows were present** in the spot check.
Determine whether historical FAAB bid amounts exist anywhere; if absent, document `faab_bid:null` as
a true source gap. The waiver standard-order → FAAB switch point is still unresolved.

### F-49 — Playoff / consolation metadata ☐ ⤴
`Matchup.is_consolation` is `0` for all playoff rows and `is_playoff` is set on every post-season
game, so all 12 teams look like they advanced each season. The dashboard returns
`made_playoffs = None` unless a season's bracket is a proper subset of the league, and the bracket
view stays caveated where it can't prove advancement. **Fix source-derived `is_consolation` /
playoff-team metadata in ff-pipeline** (prefer fixing source flags over dashboard inference);
`made_playoffs` then resolves with no contract change.

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

### 6.1 Conferences feature silently dead (functional bug; gate is green) ☐

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
- **Done when:** a 2010–2019 season's conferences endpoint returns real divisions; a 2020+ season
  still returns `available=false`; the bracket page for a conference-era season renders; gate green
  (`gen:api` drift expected clean — schema shape unchanged).

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
