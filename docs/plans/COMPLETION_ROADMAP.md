# Completion Roadmap — open scope after P12

**Purpose.** This is the forward-looking execution plan that turns the open scope captured in
`docs/ACTIVE_WORK.md` (and the 2026-06-14 doc refresh) into a sequence of **handoff-ready work
sessions**. Each session below is written so a fresh Claude Code session can pick it up cold —
context, exact files, approach, decision points, and a "Done when" — without re-deriving state.

**This doc is a PLAN artifact only.** No implementation happened in the session that wrote it.
Per `CLAUDE.md` Session model, each session below should still do its own PLAN→BUILD→VERIFY split
if it is large; small ones (S1, S2) can run as a single thread.

**Read order for any session here:** `PROGRESS.md` → this session's entry → only the doc sections
it cites → the `green-gate` skill before committing. Do **not** browse the tree; the file lists
below are deliberately exhaustive.

**Git model (non-negotiable, from global + project CLAUDE.md):** each session is a `feature/*`
branch cut from `dev`, PR'd to `dev`. Commit trailers `AI-Model` / `Prompted-By` / `Reviewed-By`;
never `Co-Authored-By: Claude`. Delete the branch after merge.

---

## Current baseline (starting state — verified 2026-06-14)

- **Application:** P0–P12 + all post-roadmap slices are merged to `dev` and promoted to `main`
  (PRs #51–#60). See `docs/archive/COMPLETED_WORK.md`.
- **One open dashboard branch:** `feature/rivalries-insights` (rivalry insight bands +
  `GET /v1/rivalries/insights`), committed and pushed but **no PR opened**.
- **Backend gate is RED on the `dev` baseline** (this is what S1 fixes — confirmed by running
  `uv run mypy src/ff_dashboard`, `uv run ruff check src/ff_dashboard`, and
  `uv run pytest tests/test_p5_matchups_unit.py`):
  - `analytics/conferences.py` — 3 mypy errors + 1 ruff error; **and the feature is silently dead
    for 2010–2019** (see S1 for the root cause).
  - `tests/test_p5_matchups_unit.py` — 2 failures (asserts removed box fields).
  - `analytics/league_history.py` — 1 ruff error (ambiguous unicode minus).

## Sequencing & dependency graph

```
S1 (baseline green + conferences repair) ──► S2 (ship rivalries-insights)
            │
            └─ unblocks a clean gate for everything after

UP program (upstream / ../danger-zone — separate repo, runs in parallel):
   S3 F-49 playoff/consolation metadata ─┐
   S4 F-27 reconstructed-scoring trust   ─┤─► S8 (league-history expansion, dashboard)
   S5 F-25 player-identity residuals     ─┤
   S6 F-37 tier 2 transactions / FAAB    ─┘
   S7 F-06 ownership succession  ⊘ BLOCKED on a source you must supply first

S8 (league-history expansion) consumes S3/S4/S6/S7 outputs; do it last.
```

**Recommended order:** S1 → S2 first (small, dashboard, unblocks the gate and lands the open
branch). Then the UP program (S3–S7) at whatever cadence the upstream repo allows; S7 needs a
human input before it can start. S8 last, once the upstream data it renders exists.

---

## S1 — Green the baseline + repair conferences  *(dashboard · do first · ~1 session)*

**Branch:** `feature/baseline-gate-green` (cut from `dev`). **Status:** ☐ ready.
**Depends on:** nothing. **Blocks:** a clean PR for S2 (which currently inherits this breakage).

### Why this exists / context
The `dev` baseline carries three gate failures that have been carried across many PRs as
"pre-existing, unrelated, left untouched." They keep the backend gate red, so every new branch
(including rivalries-insights) inherits a red gate. One of them is also a **silent product bug**.

### The three problems, with root cause

**1. `conferences.py` — written against ORM models that do not exist (the important one).**
Verified at runtime 2026-06-14:
- `from ff_pipeline.repository.models import SeasonConference, Team` → **ImportError**:
  `SeasonConference` is not a model in `ff_pipeline.repository.models`. `Team.conference_id` is
  also not mapped (`hasattr(Team, "conference_id") == False`; not in `Team.__table__.columns`).
- Because the import is wrapped in `try/except (ImportError, AttributeError)`, the module sets
  `_CONFERENCE_MODELS_AVAILABLE = False` and **every** call to `season_conferences()` returns
  `available=False, reason="no_conferences_this_season"`, and `conference_map()` returns `{}` —
  **for all seasons, including 2010–2019, which genuinely had conferences.** The feature is dead.
- The data is fine and reachable: `analytics/standings.py` (lines ~78–96) already reads the same
  two tables via **raw SQL** and works:
  ```python
  text("SELECT team_id, conference_id FROM teams WHERE season_id = :sid")
  text("SELECT conference_id, name FROM season_conferences WHERE season_id = :sid")
  ```
- mypy errors are the visible tip: `conferences.py:37,40,84` "type[Team] has no attribute
  conference_id". ruff error: `conferences.py:14` import block un-sorted.
- **Consumers to keep working:** route `GET /v1/seasons/{season_id}/conferences`
  (`api/routes/seasons.py:120`), and `analytics/bracket.py:21` imports `conference_map`.

**2. `tests/test_p5_matchups_unit.py` — asserts box fields that no longer exist.**
Two failing tests assert keys removed from `box_score()` output:
- `test_box_score_gap_delta_is_total_minus_starters` → expects `home["score_gap_delta"]`
- `test_box_lineup_score_gap_is_false_without_bonus_rules` → expects `home["lineup_score_gap"]`
`git grep "lineup_score_gap\|score_gap_delta\|has_long_td_score_gap" -- src/ff_dashboard` returns
**nothing** — the fields and the `has_long_td_score_gap` helper were removed from source, but the
tests were not updated.

**3. `league_history.py:299` — ruff RUF001 ambiguous unicode minus `−` (U+2212)** inside an
f-string used for display (`f"−{p} {label}"`), sitting next to ASCII `+` (line 297) and `→`
(line 301).

### Files that matter
- `src/ff_dashboard/analytics/conferences.py` (rewrite the two query sites)
- `src/ff_dashboard/analytics/standings.py` (lines ~78–96 — the raw-SQL pattern to copy)
- `src/ff_dashboard/analytics/bracket.py` (consumer of `conference_map` — don't break it)
- `src/ff_dashboard/api/routes/seasons.py` (the route — verify it still returns the schema)
- `tests/test_p5_matchups_unit.py` (lines ~251–263 — reconcile the two tests)
- `src/ff_dashboard/analytics/matchups.py` (`box_score()` — read its **current** output keys)
- `src/ff_dashboard/analytics/league_history.py` (line 299 — the unicode minus)
- **No conferences test exists today** (`git grep -l conference -- tests/` returns nothing — which
  is *why* the feature rotted unnoticed). S1 must **add** one (see Approach step 4).

### Approach
1. **Conferences (the real fix):** rewrite `conference_map()` and the inline team→conference
   query in `season_conferences()` to use `text()` raw SQL exactly like `standings.py`, reading
   `teams.conference_id` and `season_conferences` directly. Drop the now-unneeded
   `from ff_pipeline.repository.models import SeasonConference, Team` import, the `select` import
   if unused, and the `_CONFERENCE_MODELS_AVAILABLE` guard (the tables are always present in the
   live DB; keep a defensive `try/except` around the SQL like standings.py does, returning
   `available=False` only when the query genuinely yields nothing). Keep `get_season`,
   `list_conferences_for_season`, `require_league`, and the public function signatures unchanged.
   - **Verify it actually repairs the feature** (not just the gate): real-DB hit
     `GET /v1/seasons/{id}/conferences` for a **2010–2019** season should now return
     `available=true` with grouped divisions; a 2020+ season should still return
     `available=false, reason="no_conferences_this_season"`.
   - **Decision point:** if `list_conferences_for_season` *also* depends on a missing model and
     fails, replace it too with a raw-SQL read of `season_conferences`. Check first.
2. **Matchups tests:** read `box_score()`'s current output dict. Then either (a) the discrepancy
   info was renamed → update the two assertions to the new keys, or (b) it was removed by design →
   delete the two tests. Use `git log -p -S lineup_score_gap -- src/ff_dashboard` to confirm
   intent before deleting. Prefer matching the **shipped** behavior; do not re-add removed fields.
3. **league_history minus:** prefer `# noqa: RUF001` with a one-word comment (the glyph is
   intentional display typography matching `→`), **or** normalize to ASCII `-` if you also change
   the neighboring `+`/`→` for consistency. Do not silently change one glyph and leave the others.
4. **Add a conferences known-answer test** (`tests/dashboard/test_conferences.py` or similar,
   against the fixture DB — see `docs/08_TESTING_STRATEGY.md`): assert a conference-era season
   returns `available=true` with the expected divisions/teams, and a post-2019 season returns
   `available=false, reason="no_conferences_this_season"`. This locks in the repair so the feature
   cannot silently die again. If the existing fixture has no conference rows, extend it minimally.

### Done when
- `uv run pytest tests/dashboard -q` (and the touched root tests) green; `uv run ruff check -q`
  and `ruff format --check` clean; `uv run mypy src/ff_dashboard` clean (0 errors).
- Frontend gate unaffected (no contract change expected; run `npm run gen:api` drift check to be
  sure — conferences schema shape is unchanged).
- Real-DB click-through: a 2010–2019 season's conferences endpoint now returns real divisions;
  the bracket page for a conference-era season still renders.
- `PROGRESS.md` "Open items" §⚠ and `docs/ACTIVE_WORK.md` §6.1 ticked to ☑; `docs/10_OPEN_QUESTIONS.md`
  N6 closed.

### Read-first (token budget)
`docs/04_ANALYTICS_MODEL.md` only if you need the standings/conference metric definition; the
`green-gate` skill before committing. Nothing else.

---

## S2 — Ship the rivalries-insights branch  *(dashboard · packaging · ~1 session)*

**Branch:** `feature/rivalries-insights` (already exists). **Status:** ☐ code complete, no PR.
**Depends on:** S1 (so the inherited gate is green). **Blocks:** nothing.

### Why this exists / context
The rivalry insight bands are implemented and committed on the branch (see
`docs/plans/rivalries-insights.md` and `PROGRESS.md` "Current state"): five league-wide bands fed
by `GET /v1/rivalries/insights` (`api/routes/rivalries.py` → `analytics/rivalries.py`), pure-
presentation `web/src/features/rivalries/RivalryInsights.tsx`. Backend test file (7 tests) +
extended page test pass; the frontend gate was green at commit time. The work is done; this
session is **packaging and verification**, not building.

### Approach
1. Rebase/merge the now-green `dev` (post-S1) into `feature/rivalries-insights` so the branch's
   gate is clean on its own. Resolve any conflicts (unlikely — S1 touches conferences/matchups,
   not rivalries).
2. Run the **full** green gate once (backend pytest + ruff + mypy; frontend gen:api drift +
   typecheck + Vitest + build). Read only failures.
3. Real-DB click-through of the rivalries page: confirm all five bands render and deep-links work
   (the 2026-06-12 spot check is in `PROGRESS.md`; re-confirm post-rebase).
4. Open the PR `feature/rivalries-insights → dev` with the trailer format. Update `PROGRESS.md`
   (move the branch from "Current state / open" to merged once it lands) and
   `docs/ACTIVE_WORK.md` §1.

### Done when
Full gate green on the branch; PR open to `dev`; on merge, branch deleted (local + remote),
`PROGRESS.md`/`ACTIVE_WORK.md` updated, plan doc `docs/plans/rivalries-insights.md` moved to
`docs/archive/` (per the merged-plan convention).

### Read-first
`docs/plans/rivalries-insights.md`; the `green-gate` skill. Nothing else.

---

## UP program (S3–S7) — upstream / `../danger-zone` (Phase-1 data & research)

> These are **not dashboard PRs.** They live in the sibling `../danger-zone` (ff-pipeline) repo.
> Each, when it lands, retires one or more dashboard findings **with no dashboard code change**
> (read-only boundary) — except where a small additive dashboard consume-step is noted. Full
> finding text: `docs/reviews/2026-06-in-browser-review.md`; tracking: `docs/ACTIVE_WORK.md` §2 and
> `docs/plans/REVIEW_FIXES_ROADMAP.md`; per-program handoff: `docs/handoffs/`.
> **Prefer fixing source flags over adding dashboard inference** (an inherited project rule).

### S3 — F-49 playoff / consolation metadata  *(upstream · high product leverage)*
**Status:** ☐. **Depends on:** nothing. **Blocks:** honest `made_playoffs`, S8.
**Context.** `Matchup.is_consolation` is `0` for all playoff rows and `is_playoff` is set on every
post-season game, so all 12 teams look like they advanced every season. The dashboard therefore
returns `made_playoffs = None` unless a season's bracket is a proper subset of the league, and the
`/bracket` view (now a full championship/consolation split, PRs #55/#60) stays caveated where it
can't prove advancement.
**Approach (upstream).** In ff-pipeline, derive/correct source `is_consolation` and playoff-team
metadata so championship vs consolation games are distinguishable per season. Validate against a
couple of known brackets.
**Dashboard consume-step (small, after upstream lands).** `analytics/bracket.py` and the
`made_playoffs` derivation can then resolve without a contract change; re-verify the bracket page
and `made_playoffs` on real data. Run `gen:api` drift check (expected: no drift).
**Done when.** A representative season's championship/consolation games are correctly flagged at
source; the dashboard renders an honest bracket and non-`None` `made_playoffs` for those seasons.

### S4 — F-27 trust check on reconstructed 2010–2015 scoring  *(upstream · validation only)*
**Status:** ◐ (data landed via F-51; validation open). **Depends on:** nothing. **Blocks:** S8's
scoring-mismatch classification.
**Context.** `player_stats_scored` now spans 2010–2025 (F-51). The data half is done; what remains
is **validation**: sanity-check representative weeks, outliers, and season totals for 2010–2015
against source NFL.com / team totals before treating every reconstructed score as authoritative.
**Approach.** Pick representative weeks/teams across 2010–2015; compare reconstructed totals to
source. Document discrepancies and classify (reconstruction error vs. legitimate source variance).
**Done when.** A short validation note exists (in `../danger-zone` or `docs/handoffs/`) with the
sampled weeks, the comparison, and a go/no-go on trusting reconstructed pre-2016 scores.

### S5 — F-25 residual player-identity cleanup  *(upstream)*
**Status:** ◐ improved, not closed. **Depends on:** nothing.
**Context & exact residual counts** are in `docs/handoffs/players-audit-danger-zone.md` — **use the
status-update counts, not the original counts.** Current real-DB residuals (3048 players): D1
`last_season IS NULL` = 277; D2 league-rostered `rookie_year IS NULL` = 38; D4 never-rostered/
never-scored "ghost" players = 400 (scope-policy decision open); D3 `is_active` semantics + stale
`nfl_team` need a documented definition; D5 duplicate roster rows = 0 (resolved).
**Approach.** Rerun the audit queries from the handoff, then fix-or-document each residual upstream.
Remaining nulls/ghosts must be either fixed or explicitly recorded as **true source gaps**.
**Coordinated dashboard add (additive, optional):** expose `last_season` on `PlayerOut` once D1 is
fully populated — additive schema change, run `gen:api` drift check in the same cycle.
**Done when.** Each of D1–D4 is fixed or documented as a true source gap; D3 has a stable written
definition; the handoff's status counts are updated.

### S6 — F-37 tier 2 exact transactions & FAAB  *(upstream + small dashboard consume)*
**Status:** ◐ partly landed. **Depends on:** nothing.
**Context.** Upstream already has dated, typed transaction rows (add/drop/waiver/free-agent/trade/
draft/lineup); the dashboard renders the **derived roster-diff tier** (PR #35). Two things remain:
(1) the dashboard has not consumed the **exact** transaction dates/types as a richer tier; (2) no
**FAAB bid** rows were present in the last real-DB spot check — determine whether historical FAAB
amounts exist anywhere upstream.
**Approach.** Upstream: confirm/assemble FAAB bid data if it exists; if it does not, document
`faab_bid: null` as a true source gap and record the waiver-standard-order → FAAB switch point.
Dashboard (additive): optionally add an "exact transactions" tier alongside the roster-diff tier,
keyed off the dated rows; contract-additive, run `gen:api` drift check.
**Done when.** FAAB availability is resolved (data wired, or documented as a true gap); the switch
year is recorded; any dashboard tier added is gated honestly and gate-green.

### S7 — F-06 ownership-succession history  *(upstream · ⊘ BLOCKED — needs your input first)*
**Status:** ⊘ blocked on a source. **Depends on:** a human/source ledger you must supply.
**Context.** There are 12 persistent teams but >12 owners over time; owner ≠ team and tenures vary
(see memory `owner-vs-team-identity`). There is **no source table** for which owner held which team
across which seasons, and owner photos are a true source gap (`owner_avatar_asset_id` = 0 rows).
**Blocking input (must be resolved before S7 can build):** a ledger — even a hand-authored YAML —
of `(owner, team, season-range)`. This is the same class of input the `REVIEW_FIXES_ROADMAP.md`
"Inputs only you can supply" table tracks.
**Approach (after input).** Upstream: load the ledger into a durable table (mirror the
commissioner-history pattern: migration + seed YAML + loader + `queries.*` read helper — see the
archived `docs/archive/commissioner-history.md` for the template). Dashboard: consume via durable
human manager overrides on the manager/league surfaces.
**Done when.** Ownership succession is queryable upstream and the dashboard renders durable
manager identity instead of raw post-merge columns where appropriate.

---

## S8 — League-history expansion  *(dashboard · gated · last)*

**Branch:** `feature/league-history-expansion` (cut from `dev`). **Status:** ☐ gated.
**Depends on:** S3 (playoff-format metadata), S4 (scoring-mismatch classification), S6 (rules/
FAAB switch points), S7 (durable manager overrides). **Do this last.**

### Why this exists / context
The league-history slice is shipped (overview/timeline/eras/stories/managers + the Seasons / Rules
& Eras / Stories pages). Its **next** expansion is to consume upstream/manual identity and rules
data once it exists. A per-season **config ledger** is the missing backbone: scoring rules, season
length (1–13 → 1–14), waiver → FAAB, and ownership all changed over time and the switch-years are
TBD (see memories `league-settings-ledger`, `owner-vs-team-identity`).

### Approach
Build a per-season config ledger (scoring rules / schedule length / roster-slot settings / waiver↔
FAAB / playoff format) sourced from the upstream data the UP sessions produce, then surface it on
the Rules & Eras page with concrete change details and honest gaps where a switch-year is unknown.
Consume durable manager overrides (S7) on manager/league surfaces. Add verified scoring-mismatch
classification (S4) where the page currently shows generic provenance gaps.

### Done when
The Rules & Eras / managers surfaces render concrete, sourced settings and identity instead of
caveated gaps wherever the upstream data now exists; everything still falls back to `DataGap` (never
0/fake) where it does not; full gate green; real-DB click-through.

### Read-first
`docs/07_PAGES_AND_VIEWS.md` (the Rules & Eras / Stories sections), `docs/04_ANALYTICS_MODEL.md`
(`league_history`), `docs/05_API_CONTRACT.md` (`/v1/league/*`). Plus the memories named above.

---

## Per-session checklist (applies to every session above)

- [ ] Cut a `feature/*` branch from `dev`.
- [ ] Read only this entry + the doc sections it cites + `PROGRESS.md`.
- [ ] If the session is large, split PLAN→BUILD→VERIFY (write `docs/plans/<branch>.md` first).
- [ ] Run the **one** test file you're touching while iterating; full `green-gate` once at the end.
- [ ] No DB writes; no hand-edits to `web/src/lib/api/` (change schema + `gen:api`); never render 0
      for missing data (use `DataGap`).
- [ ] Update `PROGRESS.md` (Current state / Next / Open items) and tick `docs/ACTIVE_WORK.md`.
- [ ] Commit with `AI-Model` / `Prompted-By` / `Reviewed-By` trailers; PR to `dev`.
- [ ] On merge: delete the branch (local + remote); move any merged plan doc to `docs/archive/`.
