# HANDOFF — /seasons/ league-changes: resolve roster edits + continue categorization

> **✅ COMPLETED 2026-06-14.** The immediate task (2020/21 Chris roster edits = reserve/IR
> capacity 1→3→2) is resolved, and **all 34 canonical types are now categorized** (Decisions
> log #1–#31 in `seasons-league-changes-inventory.md`, which is the live artifact). **Next phase
> is implementation**, not more categorization — see that doc's Decisions-log STATUS header and
> the [[seasons-league-changes-inventory]] memory. This handoff is retained for history.

You are continuing a multi-session design effort. **Read this fully, then the artifacts cited.**
This thread starts cold; everything you need is here or linked.

## Read first (in order)
1. `CLAUDE.md`, `PROGRESS.md` (standard project re-entry).
2. **`docs/plans/seasons-league-changes-inventory.md`** — THE artifact. Contains: full 267-entry
   chronological list, the 34 canonical types (combined list), the evidence sheet (verbatim
   NFL.com phrasings per type), and the **Decisions log**.
3. Memory: `seasons-league-changes-inventory`, `feedback-full-control-taxonomy`.

## What this is
The `/seasons/` page (`web/src/features/league/LeagueHistoryPage.tsx`, fed by
`GET /v1/league/timeline`) shows per-season "league changes." They originate as `transactions`
rows with `transaction_type='setting_change'`: human text in `extra_data.description`, actor in
`notes`, date in `executed_at`. Extraction lives in `analytics/league_history.py`
(`_setting_changes`, `_SETTING_PATTERNS` — a 6-regex allowlist that silently drops ~88% of
entries, `_resolve_setting_gaps`). Read-only DB: **`../danger-zone/data/fantasy.db`**.

We are redesigning categorization + display. **Agreed model:**
- **3 display tiers:** T1 highlighted · T2 always-shown · T3 collapsed-but-expandable.
  Every entry is represented — nothing dropped. T3 is collapsed, not omitted.
- **Off- vs in-season split (automated):** compare `executed_at` to that NFL season's Week-1
  kickoff (kickoff date table is in the generator scripts referenced below). 267 entries =
  58 in-season / 209 off-season. Drives a visual marker, independent of tier.
- **Audience rephrasing (automated):** human label + a sentence templated from before/after.
- **Resolve vague headlines where data permits** (the method below) instead of showing
  "X updated Y" with no substance.

## Resolution method (proven this session)
Headline-only entries (no before/after in the text) can sometimes be resolved by **diffing the
real state tables across seasons and aligning on the headline's date + actor**:
- **Scoring** (`updated scoring settings`): ❌ **BLOCKED.** `scoring_rules` is one snapshot
  copied to 2011–2025 (identical fingerprint, `created_at` all 2026-05-29). Only 2010→2011
  differs (½→full PPR; pass TD 6→4). Other years unrecoverable → would need an upstream
  per-season scoring scrape (logged as a data gap).
- **Roster** (`updated roster positions`): ✅ **WORKS.** `team_rosters.roster_slot` (per
  player/week/season, `is_starter`) reveals real starting-lineup structure, which changed:
  2010 = QB·RB×2·WR×3·TE·K·DEF (no flex); 2011–2015 = 2 WR + **W/R flex**; 2016–present =
  flex widened to **R/W/T**. Headline dates align (2011-07-25 harry; 2016-08-24 Dave).

## Decisions so far (mirror of the doc's Decisions log)
1. `updated scoring settings` → **SPLIT** (T1 = derived 2010→2011 diff; T3 = hedged note for 2011–2024).
2. `updated roster positions` → **SPLIT** (T1 = concrete 2011 & 2016 diffs; 2020/21 Chris edits **pending the immediate task below**).

---

## IMMEDIATE TASK — reverse-engineer the 2020 & 2021 roster edits (Chris)
Six `updated roster positions` headlines by **Chris** produce **no** starting-lineup change:
`2020-08-24` (×2), `2020-09-02`, `2021-08-27` (×3). They touched something the starting-slot
fingerprint doesn't capture. Investigate via `team_rosters`:
- Compare **full** slot composition (incl. bench `BN`, `IR`/reserve, any new slot) and **total
  roster size per team** for **2019 vs 2020 vs 2021 vs 2022**.
- Distinct `roster_slot` values per season; per-slot counts per team (use a representative
  early week; `is_starter=0` rows are bench/IR).
- Hypotheses to test: bench size changed, IR/reserve slot added/removed, total roster size
  changed, a new slot type appeared.
- Note: 2020 Week 1 = Sep 10, so `2020-09-02` is still preseason.

**Outcome:** if a concrete change is found → rephrase it (e.g. "Bench expanded 6→7", "Added IR
slot") and ask the user for its tier. If nothing is recoverable → collapse hedged (T3) and
confirm with the user. Update the Decisions log either way.

## THEN — continue entry-by-entry categorization
Resume the doc's 34 canonical types, **one at a time, in category order (A–O)**. For each present:
plain-English meaning · volume (n / in-season / years / actors) · verbatim phrasings · whether
the headline carries before/after · and a **Resolvable?** verdict for headline-only types.
User responds with a tier (`T1`/`T2`/`T3` or `SPLIT`) or "merge with X" / "drop". Record each
in the Decisions log.

We are on entry 2 (roster). **Next is entry 3 = category C · Playoff format:** `Playoff Settings`
is rich (e.g. `'Weeks 15 & 16 - 4 teams' → 'Weeks 15,16 & 17 - 6 teams'` — encodes both bracket
weeks and field size); `updated playoff teams` (16×, all in-season) is headline-only — **verify
whether playoff field size is derivable from results/standings data per season** (caution:
memory `phase2-review-2026-06` / F-49 says playoff metadata is insufficient to infer
`made_playoffs` for some seasons, so this may be partially BLOCKED like scoring).

## Reproducing the analysis
The grouping/evidence were generated by small read-only Python scripts against the DB (the
`canon()` normalizer that folds per-manager/per-team variants, plus the Week-1 kickoff table).
Their logic is embedded in the inventory doc's generated sections; re-derive as needed — do not
trust a stale copy, re-query the DB.

## Working preferences (IMPORTANT — do not violate)
- **User wants FULL CONTROL over the taxonomy.** Present rich-but-brief context as *editable*
  proposals; go one entry at a time; let the user decide tier/merge/drop freely. **Do NOT** force
  constrained `AskUserQuestion` multiple-choice for taxonomy decisions (it was rejected twice).
- **Honesty about gaps:** never fabricate detail or render 0; use hedged notes / `DataGap` when
  data can't support a claim. Never hardcode a year window; keep it data-driven.
- Read-only DB; **no metric math in `web/`** (all logic in `analytics/`); never hand-edit the
  generated API client. Git model: `feature/*` → `dev`.
- **Status: design/planning only — no production code written yet.** Implementation (rewrite
  `_SETTING_PATTERNS` into the tiered classifier + resolution + rephrasing + off/in-season
  marker + frontend changes) comes *after* the 34 entries are categorized. The frontend already
  renders changes uniformly (per the earlier `ChangeRow` refactor on the current branch).

## Branch note
The working tree is on `feature/rivalries-insights` (unrelated open work). This league-changes
effort has produced **only docs** so far. Choose/create a branch when implementation begins.
