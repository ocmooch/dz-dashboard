# PLAN — /seasons/ league-changes: tiered classifier (IMPLEMENTATION)

**Phase:** PLAN (no code). Produced by reading the IMPL-HANDOFF + the inventory's locked
Decisions log (#1–#31) + the current code. Categorization is **done**; this plan turns the
Decisions log into function/endpoint signatures, a classifier table, the kickoff table, the
test list, and "Done when." BUILD implements against this; VERIFY runs the gate.

> **Authority:** `docs/plans/seasons-league-changes-inventory.md` Decisions log is the contract.
> Where this plan and the Decisions log ever disagree, the Decisions log wins. Do not re-tier.

---

## 0. Current state (what's already wired)

- `/seasons` → `web/src/features/league/LeagueHistoryPage.tsx` → `GET /v1/league/timeline`
  → `api/routes/league.py:get_league_timeline` → `analytics/league_history.py:league_timeline`.
- `league_timeline()` already emits, per season, a `changes.details: LeagueChangeDetail[]` list
  built from **two sources**:
  1. **State-table diffs** (the honest, fully-resolved ones): `_scoring_rule_changes`
     (from `scoring_rules`), `_roster_changes` (from `team_rosters.roster_slot`),
     league-size / season-calendar / scoring-provenance / participant diffs.
  2. **`setting_change` text** via `_setting_changes` → the **6-regex `_SETTING_PATTERNS`
     allowlist that silently drops ~88%** of the 267 rows. `_resolve_setting_gaps` then
     drops-or-rewrites headline-only roster/scoring edits.
- Schema: `LeagueChangeDetail` / `SeasonChangeFlags` / `LeagueTimelineSeason` /
  `LeagueTimeline` in `api/schemas.py` (lines ~319–378). `LeagueEras` reuses `LeagueChangeDetail`.
- Frontend `ChangeRow` refactor has landed (uniform row + "More" disclosure) — **extend it**.
- **Fixture has ZERO `setting_change` rows today** (`tests/conftest.py` seeds seasons 2015–2017
  + draft/waiver/lineup txns only). The new classifier tests need seeded `setting_change` rows.
- Existing tests live in `tests/test_league_history.py` (not under `tests/dashboard/`).

**Design decision (carry through BUILD):** replace `_SETTING_PATTERNS` + `_setting_changes`
with a dedicated module `analytics/league_changes.py`. The state-table diffs stay where they are
(they already produce the T1 roster/scoring content); the new classifier consumes the
**setting_change** stream and reconciles against those state diffs (absorb redundant headlines).

---

## A. Module & function signatures (all in `analytics/`)

New file: `src/ff_dashboard/analytics/league_changes.py`.

```python
# ---- canonical classification ----
@dataclass(frozen=True)
class RawSettingChange:
    season_id: int          # filed season_id (NOT necessarily display season)
    year: int               # filed year
    executed_at: datetime | None
    description: str         # extra_data.description, verbatim
    actor: str | None        # from notes, else parsed from description prefix

def classify(raw: RawSettingChange) -> ClassifiedChange:
    """Map one row → canonical_type + per-type spec via _TYPE_SPECS.
    Unmatched/future types degrade to T3 + missing_context with raw text (catch-all)."""

@dataclass(frozen=True)
class ClassifiedChange:
    canonical_type: str
    category: str            # reuse existing taxonomy where possible
    tier: str                # "T1" | "T2" | "T3"
    human_label: str
    summary: str             # rephrased sentence (templated from before/after)
    before: str | None
    after: str | None
    phase: str               # "in_season" | "off_season"
    changed_at: str | None   # ISO
    actor: str | None
    event_group_key: str | None   # set when this row aggregates into an event
    display_season_id: int        # = season_id except re-attribution (F)
    missing_context: bool
    source: str
    certainty: str

# ---- phase ----
WEEK1_KICKOFF: dict[int, date]    # constant table, section D
def phase_for(executed_at, filed_season_year) -> str   # vs kickoff of FILED season

# ---- aggregation (aggregate-to-elevated-event) ----
def aggregate(changes: list[ClassifiedChange]) -> list[Event]
    """Collapse same-day/same-type clusters keyed by event_group_key into ONE elevated
    event; individual rows preserved as `members` (T3) for expand-on-click."""

# ---- resolution helpers (data-driven; reuse league_history internals) ----
# Roster reserve/IR + starting diffs already exist as _roster_signatures/_roster_changes.
# Scoring 2010->2011 diff already exists as _scoring_rule_changes.
# This module does NOT recompute them; it ABSORBS the matching headlines (see treatment
# RESOLVE_FROM_STATE) so the state diff is the single shown explanation.

# ---- public entrypoint (replaces _setting_changes) ----
def setting_change_events(
    session, *, roster_resolved_cats: dict[int, set[str]]
) -> dict[int, list[dict[str, Any]]]:
    """Per DISPLAY-season list of emitted change/event dicts (post-classify, post-aggregate,
    post-reattribute). Keyed by display year. Shape matches the extended LeagueChangeDetail."""
```

`league_history.py:league_timeline()` changes:
- delete `_SETTING_PATTERNS`, `_setting_changes`, and the schedule-collapse block inside it
  (schedule collapse now handled generically by `aggregate`).
- keep `_resolve_setting_gaps` ONLY if still needed for the state-derived roster/scoring
  headline absorb; otherwise fold its drop-or-rewrite into `RESOLVE_FROM_STATE`/`HEDGED`.
- replace `details.extend(setting_changes.get(year, []))` with
  `details.extend(setting_change_events(...).get(display_year, []))`.
- pass which categories already have a state-derived diff this season so the classifier can
  absorb the redundant headline (mirrors the current `_resolve_setting_gaps` derived-cats set).

---

## B. Classifier table (canonical_type → tier · label · treatment)

Distilled from Decisions #1–#31. **Treatment** verbs:
`PASS` = parse `from 'x' to 'y'`, emit before/after + templated sentence ·
`STATE` = defer to existing state-table diff, absorb headline ·
`HEDGE` = T3 + `missing_context`, name actor+date, "specifics not recorded" ·
`MISSING` = headline-only, T2 + `missing_context` marker (actor/date) ·
`AGG(key→tier)` = individually T3, collapse to one elevated event ·
`MERGE` = two types same day → one event ·
`COLLAPSE` = routine, rolls into the per-season T3 bucket.

| # | canonical_type | tier | label | treatment |
|---|---|:--:|---|---|
| 1 | scoring_settings | SPLIT | Scoring settings | 2010→11: **STATE** (T1 via `_scoring_rule_changes`, ½→full PPR, passTD 6→4); else **HEDGE** (T3) |
| 2 | roster_positions | T1 | Roster positions / Roster: reserve slots | **STATE** (starting + reserve/IR diffs from `team_rosters`) |
| 3 | playoff_settings | T1 | Playoff format | **PASS** (before/after carries weeks+field) |
| 4 | playoff_teams | T2 | Playoff field | **MISSING** (field size not derivable; actor/date marker) |
| 5 | waiver_faab (=waiver_type+waiver_budget) | T1 | Waiver system | **MERGE** same-day → "Switched to FAAB ($100 budget)" |
| 6 | waiver_period | T2 | Waiver period | **PASS** |
| 7 | trade_review_type | SPLIT | Trade approval | T2 = 2010 & 2011 transitions (**PASS**); T3 = 2023–25 re-confirms (**COLLAPSE**, one note) |
| 8 | trade_deadline | SPLIT | Trade deadline | T1 = 2019 first-ever (No Deadline→date, **PASS**); T3 = 2011 net-zero shuffle (**COLLAPSE**) |
| 9 | trade_reject_time | T2 | Trade reject window | **PASS** |
| 10 | fee | T2 | Entry fee | **PASS** timeline; **2013-08-05 entry** gets "last NFL.com-recorded buy-in" note |
| 11 | standings_tiebreaker | T2 | Tiebreaker | **PASS** + legacy best-of-3 note; 2018 is re-confirmation not flip |
| 12 | post_draft_players | T2 | Post-draft players | **PASS** + "in place since 2010" (originating standard) |
| 13 | undroppable_list | T2 | Undroppable list | **PASS** + originating-standard affordance |
| 14 | draft_type | T3 | Draft format | **COLLAPSE** (offline→live annual default-reset) |
| 15 | draft_time | T3 | Draft scheduling | **COLLAPSE** |
| 16 | draft_order | T3 | Draft order | **COLLAPSE** |
| 17 | draft_order_randomized | T3 | Draft order | **COLLAPSE** |
| 18 | time_per_pick | SPLIT | Pick clock | T2 = era changes 15s(2017–19)→120s(2020+) (**PASS**); T3 = 300s/90s blips (**COLLAPSE**) |
| 19 | draft_reset | T3 | Draft reset | **COLLAPSE** |
| 20 | draft_board | T2 | Draft board | **MISSING** (ambiguous, 2018-09-02) |
| 21 | schedule_week_edit | AGG(`sched-{year}-{date}`→T2) | Schedule rebuild | 2014 13× → one T2 "Rebuilt the Week 1–13 schedule" |
| 22 | division_assignment | AGG(`div-{year}-{date}`→T1) | Division realignment | 4 same-day clusters → one T1 each (before/after lists who moved) |
| 23 | edit_story_permission | T3 | Permission toggle | **COLLAPSE** |
| 24 | edit_poll_permission | T3 | Permission toggle | **COLLAPSE** |
| 25 | logo_lock + lineup_lock | AGG(`punish-2012`→T2) | Commissioner penalty | 2012 → one T2 "locked mike's logo & lineup after offensive team name" |
| 26 | waiver_priority | AGG(`wpri-2018-10-09`→T2) | Waiver priority | 2018 reorder (10 rows) → one T2; 2017 trivial 2-team swap stays T3 COLLAPSE |
| 27 | waiver_budget_team | T2 | Per-team FAAB | mechanics clear (39→76), cause not recoverable → T2 + honest note |
| 28 | adjusted_points | AGG(`adjpts-2021-wk17`→T1) | Manual scoring adjustment | 4× → one T1; **RE-ATTRIBUTE to 2021** (section F) |
| 29 | player_adds_count | T3 | Add-count correction | **COLLAPSE** (counter reset) |
| 30 | player_trades_count | T3 | Trade-count correction | **COLLAPSE** (counter reset) |
| 31 | mgmt_privileges_assigned + removed | AGG(`commish-handoff`→T1) | Commissioner change | collapse to T1 succession events; filter co-manager noise; **xref `commissioners` table, don't duplicate** |
| — | **catch-all** | T3 | (raw) | **HEDGE** + `missing_context`, verbatim text — never drop |

**SPLIT resolution rule** (which branch fires): keyed on recoverable detail per the Decisions
log notes — #1 by year (2010→11 only), #7 by year (≤2011 vs ≥2023), #8 by before-state
(`No Deadline` → T1) , #18 by value (steady-state era vs reverted-within-days blip).

---

## C. Audience rephrasing

- Each **PASS** type: `human_label` + a sentence from parsed before/after, e.g.
  `Draft format` → "Moved to a live online draft (was offline)."; `Entry fee` → "Buy-in
  raised to $125 (was $100)." Templates live next to `_TYPE_SPECS`.
- **MISSING / HEDGE / catch-all**: source-limited fallback naming actor + date, e.g.
  "{actor} finalized the playoff field on {date}; NFL.com records the action but not the
  field size." Sets `missing_context=True`.
- **AGG events**: a single headline sentence per the Decisions log wording (#21, #22, #25,
  #26, #28, #31), with `members` carrying every underlying row verbatim.
- **Originating standards** (#12, #13, and any single founding config unchanged since 2010):
  add an "in place since {year}" affordance.

---

## D. Off- vs in-season marker (kickoff table + oracle)

Embed `WEEK1_KICKOFF` (NFL Thursday opener per season). **Validated against the inventory's
267-row `phase` column** — every boundary below falls between that season's last `off` and
first `IN` row:

| yr | kickoff | yr | kickoff | yr | kickoff | yr | kickoff |
|--|--|--|--|--|--|--|--|
| 2010 | 09-09 | 2014 | 09-04 | 2018 | 09-06 | 2022 | 09-08 |
| 2011 | 09-08 | 2015 | 09-10 | 2019 | 09-05 | 2023 | 09-07 |
| 2012 | 09-05 | 2016 | 09-08 | 2020 | 09-10 | 2024 | 09-05 |
| 2013 | 09-05 | 2017 | 09-07 | 2021 | 09-09 | 2025 | 09-04 |

`phase_for(executed_at, filed_year)` = `off_season` if `executed_at.date() < WEEK1_KICKOFF[filed_year]`
else `in_season`. **Compute against the FILED season's kickoff** (not the re-attributed display
season) — this matches the oracle, which marks the 2022-01-16 Adjusted-Pts rows `off`
(Jan 2022 < 2022 kickoff) even though they re-attribute to the 2021 display bucket. Future
years missing from the table fall back to a Sept-1 sentinel + a code comment to extend it.
In-season T1/T2 events keep the marker and are **never down-tiered** for timing.

---

## E. Aggregate-to-elevated-event

`aggregate()` groups classified rows by `event_group_key` and emits ONE `Event` per group at
the spec'd tier, with `members=[underlying rows]` (each T3, expandable). Six instances:
division realignments (4× → T1), 2014 schedule rebuild (→ T2), commissioner handoffs (→ T1),
2012 logo/lineup-lock punishment (→ T2), 2018 waiver-priority reorder (→ T2), 2021 Adjusted-Pts
(→ T1). Non-aggregated T3 rows roll into the existing per-season "N routine changes" bucket
(also `members`-backed).

---

## F. Season re-attribution

Route emitted events by `executed_at` + `effective_week`, not raw `season_id`. The 4
`Adjusted Pts For Week 17` rows are filed `season_id=2022` but belong to **2021** (2021 playoffs
= wk 15–17). `display_season_id` = 2021 for that event; **phase stays computed vs 2022 kickoff**
(section D). Implement as a small re-attribution rule keyed on canonical_type + Jan-window date,
documented inline. (Verified: 2021 champ was scott def. DJ — the #28 "needs revision" condition
does not fire; standard T1 representation.)

---

## G. API contract (extend, then regen)

Extend `LeagueChangeDetail` in `api/schemas.py` with **optional, defaulted** fields so existing
state-derived details stay valid:

```python
tier: str = "T3"                       # "T1" | "T2" | "T3"
human_label: str | None = None
phase: str | None = None               # "in_season" | "off_season"
event_group_key: str | None = None
missing_context: bool = False
members: list["LeagueChangeDetail"] = []   # underlying rows for aggregated/collapsed events
canonical_type: str | None = None
```

State-derived details (roster/scoring/league-size/etc.) get a tier from a small mapping
(roster/scoring/playoffs → T1; schedule/standings/waiver → T2; data_quality/provenance → T3)
so the frontend can tier uniformly. Then **`cd web && npm run gen:api && git diff --exit-code
web/src/lib/api`** — never hand-edit the client.

---

## H. Frontend (`LeagueHistoryPage.tsx`, extend `ChangeRow`)

- Render **3 tiers**: T1 highlighted (headlined, accent rule), T2 always-shown, T3 collapsed
  under one per-season "N routine changes" group, **expandable** to show every `member` row.
- **In-season marker** chip on `phase==="in_season"` events.
- **`missing_context`** → reuse the `DataGap`/"More" affordance text ("source records the
  action but not the values"). Never render 0.
- Aggregated events show the headline + an expander listing `members`.
- Keep the existing category color/legend; add tier styling. Pure presentation, **zero math**.

---

## I. Tests (fixture-DB known answers)

**Fixture work first:** add `setting_change` `Transaction` rows to `tests/conftest.py` covering
≥1 representative of each treatment branch (PASS, STATE-absorb, HEDGE, MISSING, each AGG, MERGE,
COLLAPSE, catch-all, the 2021 re-attribution, an in-season + an off-season row). Seasons in the
fixture are 2015–2017 + upcoming; extend as needed (and/or add reserve/IR roster rows to assert
the 1→3→2 diff, plus a 2010/2011 scoring-rule pair).

Backend (`tests/test_league_history.py`, or a new `tests/test_league_changes.py`):
1. `classify` tier/label/treatment per representative canonical_type (table B).
2. SPLIT branch selection (#1/#7/#8/#18).
3. `phase_for` against the kickoff table — **regression vs the 267-row oracle** (drive a
   parametrized check from the inventory's chronological list).
4. Resolution diffs: roster reserve/IR 1→3→2; starting 3WR→2WR+flex, flex→R/W/T; scoring
   2010→2011.
5. `aggregate`: each of the 6 elevated events collapses correctly; `members` retained.
6. Re-attribution: Adjusted-Pts event lands under display year 2021, phase `off_season`.
7. **Nothing dropped:** count emitted (events + members) == count of input setting_change rows.
8. Catch-all: an unknown description → T3 + `missing_context` + verbatim text.
9. API contract test for the new schema fields (envelope shape).

Frontend (`web/src/features/league/league.test.tsx`): 3-tier render, T3 expand reveals members,
in-season marker, `missing_context` affordance. e2e click-through of `/seasons/` in VERIFY only.

---

## J. Branch & housekeeping

- Working tree is on `feature/rivalries-insights` (unrelated). **BUILD must cut
  `feature/seasons-league-changes` from `dev` first** — do not build on the rivalries branch.
- Commit trailers `AI-Model`/`Prompted-By`/`Reviewed-By`; **never** `Co-Authored-By: Claude`.
- Update `PROGRESS.md` (Current state + Files that matter now) as BUILD progresses.
- This is **docs-only**; commit this plan on the current state per the session model (PLAN
  produces only the plan file).

---

## Done when (this milestone)

- All 267 entries represented at their Decisions-log tier; **nothing dropped**; T3/aggregate
  groups expand to every underlying row.
- Classifier, resolution, rephrasing, in/off marker, aggregation (6 events), and 2021
  re-attribution work on the **real DB** (`../danger-zone/data/fantasy.db`) — not just fixture;
  gaps show honest affordances, no rendered 0s.
- `LeagueChangeDetail` extended; `gen:api` drift check clean.
- Full green gate (backend pytest+ruff+mypy; frontend gen:api drift + typecheck+lint+test;
  e2e where called for). `/seasons/` clicked through. `PROGRESS.md` updated; committed.

## Open questions to surface during BUILD (ask, don't invent)
- Exact rephrasing wording for any type whose template the inventory leaves implicit.
- Whether the per-season T3 "N routine changes" bucket should sit above or below the T1/T2
  events visually (a presentation call, not a taxonomy one).
- Any canonical_type the live DB surfaces that isn't in the 34 (catch-all handles it as T3, but
  flag for a real decision).
