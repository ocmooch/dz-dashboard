# HANDOFF — /seasons/ league-changes: IMPLEMENTATION phase

You are implementing a design that is **already fully decided**. This thread starts cold;
everything you need is here or in the cited artifacts. **Do not re-do categorization** — the
34 types are categorized and the per-type spec is locked. Your job is to build it.

## Read first (in order)
1. `CLAUDE.md`, `PROGRESS.md` (standard re-entry + token discipline).
2. **`docs/plans/seasons-league-changes-inventory.md`** — THE artifact. The **Decisions log**
   (#1–#31, with the STATUS header + tier rollup) is the **authoritative per-type spec**:
   tier (T1/T2/T3/SPLIT), human label, rephrasing, aggregation, resolution, missing-context.
   Also has the 267-row chronological list (with `phase` IN/off per row — your phase oracle),
   the evidence sheet (verbatim phrasings to match), the **Data gaps** list, and the
   **Concept notes** (aggregate-to-elevated-event; originating standards).
3. Memories: `seasons-league-changes-inventory`, `feedback-full-control-taxonomy`,
   `phase2-standings-tiebreak`, `league-settings-ledger`, `phase2-architecture`.
4. Doc sections (by section, not whole): `05_API_CONTRACT` (timeline endpoint shape),
   `07_PAGES_AND_VIEWS` (/seasons/ page), `04_ANALYTICS_MODEL` (league_history §),
   `03_DATA_ACCESS` (gap table + read-only rules).
5. Code to read before touching: `src/ff_dashboard/analytics/league_history.py`
   (`_setting_changes`, `_SETTING_PATTERNS`, `_resolve_setting_gaps`); the `/v1/league/timeline`
   route + its pydantic schema in `api/`; `web/src/features/league/LeagueHistoryPage.tsx`
   (the `ChangeRow` refactor already landed — extend it, don't rebuild).

## What this is
The `/seasons/` page shows per-season "league changes" sourced from `transactions` rows with
`transaction_type='setting_change'` (human text in `extra_data.description`, actor in `notes`,
date in `executed_at`). Today `_SETTING_PATTERNS` is a **6-regex allowlist that silently drops
~88%** of the 267 entries. We are replacing it with a full, auditable tiered classifier where
**nothing is dropped**. Read-only DB: **`../danger-zone/data/fantasy.db`** (verify on the real
DB, not just the fixture — see the stale-DB lesson in memory).

## Scope — build these (all logic in `analytics/`, zero math in `web/`)

**A. Tiered classifier (replaces `_SETTING_PATTERNS`).** Map every `setting_change` to:
`canonical_type · category · tier (T1/T2/T3) · human_label · rephrased_sentence · phase
(in/off) · event_group_key · season_override · missing_context flag`. Implement the Decisions
log exactly. **Catch-all required:** an unmatched/future type degrades to T3 with its raw text —
honest, never omitted. Several types are SPLIT (tier depends on recoverable detail) — see #1,
#2, #7, #8, #18.

**B. Resolution helpers (data-driven, never hardcode a year).**
- **Roster** (#2): from `team_rosters.roster_slot` per season — starting-slot structure
  (2011 +W/R flex, 2016 flex→R/W/T) and **reserve/IR capacity** = max simultaneous `RES` per
  team per season (1 for 2011–19 → 3 in 2020 → 2 from 2021). Emit before/after diffs.
- **Scoring** (#1): 2010→2011 diff from `scoring_rules`; all other years hedged (snapshot gap).
- Compute these in analytics from the DB; don't bake constants.

**C. Audience rephrasing.** Human label + a sentence templated from parsed before/after
(examples in the inventory's "Audience rephrasing" §). Headline-only types get the
source-limited / missing-context fallback naming actor+date.

**D. Off- vs in-season marker.** Compare `executed_at` to that season's **NFL Week-1 kickoff**.
You must embed a per-season Week-1 kickoff table (small constant). **Validate it against the
inventory's `phase` column** (267 rows already labelled IN/off → your regression oracle).

**E. Aggregate-to-elevated-event.** Collapse same-day/same-type clusters into ONE event:
Division realignments→T1 (4 clusters), 2014 schedule rebuild→T2, commissioner handoffs→T1,
2012 logo/lineup-lock punishment→T2, 2018 waiver-priority reorder→T2, 2021 Adjusted-Pts→T1.
Individual rows stay T3 underneath the event.

**F. Season re-attribution.** Route by `executed_at` date + `effective_week`, **not** raw
`season_id` — the 4 "Adjusted Pts Wk17" rows are filed under 2022 but belong to **2021** (#28).

**G. API contract.** Extend the `/v1/league/timeline` pydantic schema (tier, phase, label,
sentence, grouped events, `missing_context`). Then `npm run gen:api` + drift check. **Never
hand-edit `web/src/lib/api/`.**

**H. Frontend.** Render the 3 tiers (T1 highlighted · T2 always-shown · T3 collapsed-but-
expandable group per season), the in-season marker, and a `DataGap`/"missing context"
affordance for unrecoverable types. Never render 0 for missing data.

## Tests (fixture-DB known answers)
- Analytics unit tests: tier assignment per representative type; resolution diffs (roster
  reserve/IR 1→3→2, scoring 2010→11); aggregation grouping; phase classification vs the 267-row
  oracle; the 2021 re-attribution.
- API contract test for the new schema; frontend component tests for the 3 tiers + gap
  affordance; e2e click-through in VERIFY only.

## Constraints (non-negotiable)
- Read-only DB; **no metric math in `web/`**; never hand-edit the generated client; run the
  `gen:api` drift check; full **green gate** before commit (use the `green-gate` skill).
- Data gaps → honest affordances, never fabricate or render 0. Keep everything **data-driven**;
  never hardcode a year window (the unscored gap keys on the per-season `is_scored` flag).
- Git model `feature/*` → `dev`; commit trailers `AI-Model`/`Prompted-By`/`Reviewed-By`,
  **never** `Co-Authored-By: Claude`.

## Working preferences
- The user wants **full control**: the Decisions log is the contract — implement it, don't
  re-tier. If a genuine ambiguity surfaces mid-build (a type the log doesn't cover, or a
  rephrasing wording call), **ask** rather than invent. Don't force constrained multiple-choice
  for any taxonomy-shaped decision.

## Session split (per CLAUDE.md session model)
- **PLAN:** write `docs/plans/seasons-league-changes-IMPL-PLAN.md` — function/endpoint
  signatures, the new schema shape, the classifier table (type→tier/label/treatment distilled
  from the Decisions log), the kickoff table, the test list, and "Done when." Commit. No code.
- **BUILD:** implement A–H against the plan; update `PROGRESS.md` as you go; checkpoint+stop if
  context tightens.
- **VERIFY:** green gate, manual click-through of `/seasons/`, commit with trailers.

## Branch
The effort is **docs-only so far**. Create **`feature/seasons-league-changes` from `dev`** when
BUILD starts. The working tree may be on `feature/rivalries-insights` (unrelated) — don't build
on top of it.

## Done when
- Every one of the 267 entries is represented at its Decisions-log tier (nothing dropped);
  T3 collapses expand to show every underlying row.
- Resolution, rephrasing, in/off marker, aggregation, and 2021 re-attribution all work on the
  **real DB**; gaps show honest affordances.
- Green gate fully green; `/seasons/` clicked through; `PROGRESS.md` updated; committed.
