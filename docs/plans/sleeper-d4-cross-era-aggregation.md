# Sleeper D4: cross-era aggregation audit (plan)

Scope: `docs/sleeper/02` §D4; rules in `01` §5, helper shapes in `01` §4. Built on the mixed-era
fixture. Branch `feature/sleeper-d4-cross-era-aggregation` (from `dev` after D3, PR #130).

**Done when (verbatim):** every cross-season payload carries an aggregation note where it excluded or
normalized anything; no cross-era number silently mixes incomparable inputs.

## What the audit found (probed 2026-11-10, after D3)

Method: grep for season loops / unscoped `select(Matchup)` / `GROUP BY owner` in the D4 modules, then a
leak scan that replays all 406 golden routes (legacy + every season/team route re-pointed at 2026)
on the mixed fixture and looks for the unfinished week's live scores in the responses.

- **Leaks of the unfinished week (D3 rule) still present:**
  - `league_history._unique_games` → `/v1/league/stories` (a week-9 live score appears in a story);
  - `weekly_scores.weekly_scores` → `/v1/seasons/{id}/weekly-scores` (week-9 live scores plotted);
  - `owners.owner_consistency` (pools week-9 live scores into the weekly profile; invisible to the
    scan because only derived rates are emitted).
- **Already era-correct through D3:** careers / owner seasons / teams index (via
  `compute_standings`), h2h + all rivalries + owner story (via `all_pairwise`), power (via standings
  `through_week`), records book.
- **No cross-era transaction-activity metric exists today.** The only move counting is per
  team-season (`teams.team_transactions`, `transactions.derive_roster_moves`). The `01` §5 activity
  rule therefore gets a shared helper + tests now, and its first cross-era consumer in D6.
- **No cross-era FAAB comparison exists today** (`team_faab_budget` is per team-season). Same: a
  helper now, consumers in D6 (`faab_market.py`).
- **Scoring-rule eras on the live DB:** rule changes in 2011 and 2021 (`league_timeline`
  `scoring_rules` category), plus the 2026 Sleeper rules (`00` §4) → 4 scoring eras: 2010, 2011–20,
  2021–25, 2026–. Records rows today carry no rules-era marker.

## Design

### `analytics/aggregation.py` (new, pure where possible)

```python
def seasons_with(session, capability: str) -> set[int]          # season_ids whose capability is showable
def counted_seasons(session) -> dict[int, int | None]            # played season_id -> through_week (None = final)
def scoring_eras(session) -> dict[int, ScoringEra]              # season_year -> {era_id, label "2011–2020", start, end}
def is_move(txn) -> bool                                        # add/drop/waiver/trade, not failed, has a player
def pct_of_budget(spend: float, budget: float | None) -> float | None
def normalize_within_season(rows, field, key="season_id") -> list[dict]   # adds f"{field}_z"
def aggregation_note(used, excluded, reason, partial=None) -> dict | None # None when nothing excluded/partial
```

- `scoring_eras` groups contiguous seasons by their scoring-rule signature (reuses
  `league_history._scoring_rules_by_season` / `_rule_signature`, moved or imported, not duplicated).
  A season with no stored rules joins no era (`None`): never guessed.
- `AggregationNote` schema: `{used_seasons: [int], excluded_seasons: [int], partial_seasons:
  [{season_year, through_week}], reason: str}`. `partial_seasons` is the D3 addition: an in-progress
  season counted through its last final week (user rule: current state, marked subject to change).
  Additive optional field on each payload below; `None` when nothing was excluded, partial or
  normalized (so legacy goldens stay identical).

### Decisions per metric (the inventory)

| Payload (route) | Spans | Rule (`01` §5) | Change | Note when |
|---|---|---|---|---|
| owner career / seasons / list / teams index (`/owners*`, `/teams`) | all seasons | sum W-L-T, titles, Sackos, playoffs directly | none to values | 2026 partial |
| owner consistency (`/owners/{id}` profile) | all weeks | week-relative ranks: comparable | **drop pending weeks** | 2026 partial |
| owner trajectory / story | all seasons | sum directly | none (already D3-clean) | 2026 partial |
| h2h, rivalry matrix/insights/streaks/nemeses | all games | sum directly | none (D3-clean) | 2026 partial |
| records book (`/records`) | all seasons | compare directly + **rules-era marker** | add `scoring_era` to each season-scoped row | season-PF excludes 2026 (D3); player records = scored era |
| league stories (`/league/stories`) | all games | compare directly + rules-era marker | **drop pending weeks**; add `scoring_era` | 2026 partial |
| league overview / timeline / eras | all seasons | structural counts | none | none |
| weekly scores (`/seasons/{id}/weekly-scores`) | one season | n/a (season-scoped) | **drop pending weeks** (D3 leak) | none |
| efficiency, power, insights | one season | n/a | none | none |
| team transactions / roster moves | one team-season | activity = moves only | use `is_move` (replaces the D3 inline filter) | none |
| FAAB budget | one team-season | raw $ per season | none; `pct_of_budget` ready for D6 | none |
| draft (`/seasons/{id}/draft`, tendencies) | tendencies span seasons | unchanged; draft type as a label | add `draft_type` (`snake`/`auction`/null) per season from `settings_snapshot` (Sleeper) | none |

Rows marked "none to values" change no legacy number, so the parity suites stay green with **no**
golden regeneration. If the build finds a legacy value that must move, it stops and lists it for the
user (the `02` D4 rule).

### Frontend

- `AggregationNote` → one small `ProvenanceNote` line under the affected card
  ("Includes 2026 through week 8." / "Season totals exclude 2026, in progress."). Copy in
  `lib/platform.ts`; nothing rendered when the note is null.
- Records + Stories: a neutral rules-era chip on each row ("2011–20 scoring"), only when the book
  spans more than one scoring era. No colour by era (the `03` era-marker rule).

## Files

- New: `analytics/aggregation.py`, `tests/test_d4_aggregation.py`.
- Changed: `owners.py`, `records.py`, `league_history.py`, `weekly_scores.py`, `teams.py`,
  `draft.py`, `api/schemas.py` (`AggregationNote`, optional `aggregation_note` / `scoring_era` /
  `draft_type`); `web/`: Records, Stories, Manager profile, Managers/Teams index, regenerated client.

## Tests

Unit (`test_d4_aggregation.py`), one per `01` §5 rule:
- W-L-T sum across eras: a shared owner's career = legacy seasons + 2026 weeks 1–8 (hand sum).
- PF/records compare directly; a record row carries the right `scoring_era`; `scoring_eras` on a
  fixture with one rule change splits into two eras; a season with no rules → `None`.
- `is_move`: lineup_change / setting_change / failed claim / player-less pick leg → False; legacy
  add/drop/trade and Sleeper waiver_add → True. Legacy lineup view (`derive_roster_moves`) unchanged.
- `pct_of_budget`: $37 of $100 → 0.37; budget None → None (never 0).
- `normalize_within_season`: z-scores per season, single-row season → None.
- `aggregation_note`: None when nothing excluded; partial 2026 listed with `through_week=8`.

BFF on the mixed fixture:
- the leak scan as a test: no route's payload contains a week-9 live score (temp copy with sentinel
  scores like 987.65 so the check is exact);
- owner careers include 2026 finalized games; `aggregation_note.partial_seasons` names 2026/8;
- legacy-only fixture: every new note is null (parity unchanged).

Both golden parity suites green with no regeneration.

## Decided with the user (2026-11-10)

1. **Rules-era marker = scoring-rule changes** (2010 | 2011–20 | 2021–25 | 2026–), not just the
   platform switch. `01` §5 says rule changes inside the NFL.com era already count.
2. **Careers include the in-progress season's finalized games**, with the "through week N" note
   (the D3 rule applied to careers), rather than leaving 2026 out until it ends.
3. **Season-total records (best/worst season PF) skip the in-progress season** (as D3 shipped), with
   the note saying so.

All three confirmed as proposed.
