# Handoff → Data Coverage & Relevance Matrix (the paramount deliverable)

**Read `00-data-integrity-program.md` first, and run `player-identity-resolution.md` before
finalizing the relevance scope** (the matrix's relevance is identity-cluster-aware). · **Status:**
☐ · **Repo:** `dz-dashboard` (BFF, read-only) + a small read-only helper in `../danger-zone`
`queries.py` if needed. · **Builds on:** the existing `analytics/coverage.py` + `/v1/meta`. ·
**Authored:** 2026-06-16 against the live DB.

## Goal

One **data-driven, queryable, tested** artifact that is the single source of truth for two
questions the codebase currently answers ad-hoc, page by page:

1. **Relevance** — *which entities belong to this league at all?* (Seasons 2010+, the league's
   teams, its owners, and the players ever on a league roster — by resolved identity cluster.)
   Everything else (the ~3,000 non-league players, the 1,403 scored-but-never-rostered records,
   pre-2010 injury rows) is excluded **visibly and auditably**, not silently dropped.
2. **Coverage** — *for a relevant entity, which feeds have data, for which season/week?* (Scored
   stats, projections, injuries, player_status/availability, rosters, transactions, NFL game
   status, DST.)

The matrix then **instructs both layers**: the BFF consults it to know whether to attempt a field;
the UI uses it to render a `DataGap` that *explains itself* ("Projections not captured for 2017")
instead of a bare `—`. This is the structural fix for the whack-a-mole pattern: it converts silent
absence back into a declared, tested signal.

## Why this is paramount, not a nicety

Every recent symptom — blank Proj/Value on 2017 W7, status badges on the wrong weeks, DATA flags on
reconstructed weeks — is a *coverage* fact that no one could see without navigating to it. The
matrix makes coverage **first-class**: declared once, tested, and surfaced. Features stop being
"done because this page looks right" and start being "done because they render correctly across the
declared envelope and gap honestly outside it" (the principle in the program doc → write it into
`docs/08_TESTING_STRATEGY.md`).

---

## Coverage truth as measured (2026-06-16 — the matrix must *derive* this, never hardcode years)

Per the hard rule "the unscored gap is data-driven on the per-season `is_scored` flag — never
hardcode a year," the matrix is **computed from the DB every run**. These numbers are the
known-answer fixtures for the contract test, not constants to embed:

| Feed | Season range present | Granularity note |
|------|----------------------|------------------|
| `team_rosters` | 2010–2026 (2026 preseason, ~193 rows) | full; the relevance anchor |
| `player_stats_scored` | 2010–2025 (no 2026 yet) | ~6.5–7.5k rows/season — **far exceeds rostered** (≈2× ), i.e. carries non-league players |
| `player_injury_reports` | **2009**–2025 (no 2026) | 2009 is **pre-league** → must be excluded by relevance |
| `projections` | **week 1 only** of 2024, 2025, 2026 | only **2025** has `projected_points`; 2024/2026 only `projected_stats` |
| `transactions` | (verify range; some seasons sparse — see memory `2010-transactions-null-effective-week`) | 2010 wk2–8 effective_week gaps |
| `player_status` / availability | current-season only (see `coverage.py: AVAILABILITY_CURRENT_SEASON_ONLY`) + NFL.com current-state-drift caveat | source property, not detectable per-run |

Relevance footprint: **4,286 players total, 1,247 ever rostered.** The matrix's player axis is the
1,247 (by cluster), not the 4,286.

---

## Design

### 1. Separate the two axes — do not conflate relevance and coverage

- **Relevance** answers "should this row exist in any league-scoped view?" It is a *membership*
  fact. Anchor: a player is league-relevant iff its **resolved identity cluster** (workstream 1)
  has ≥1 `team_rosters` row in a league season (2010+). Teams: the league's persistent franchises
  (see memory `owner-vs-team-identity` — 12 teams, >12 owners). Seasons: those with played games
  (`played_season_ids`, already in `analytics/common.py`). Weeks: per-season format
  (1–13 vs 1–14 regular + playoffs — see F-32 / `league-settings-ledger`).
- **Coverage** answers "for a relevant entity, does feed F have data at season/week?" It is a
  *population* fact, derived by querying each feed scoped to the relevant set.

Keeping them separate is what prevents the two classic failures: leaking non-league rows (relevance
too loose) and hiding stranded stats-twins (relevance applied to raw ids instead of clusters).

### 2. The relevance boundary is explicit and auditable (not a silent WHERE clause)

The prior leakage happened because exclusion was implicit and breakable (D4: the era filter was
defeated by NULL `last_season`). The matrix must **record what it excludes and why**, so the
boundary is testable. Emit, alongside the included set, the exclusion tallies:
non-league players, pre-league rows (e.g. 2009 injuries), scored-but-never-rostered records,
unresolved identity-split candidates. A regression test asserts these counts and asserts **no
excluded entity appears in any league-scoped index endpoint**.

### 3. Status vocabulary + reason codes (drive the self-explaining gap)

For each (axis-cell × feed): one of
`present` · `partial` · `absent` · `not_applicable`, plus a machine reason the UI renders:

| reason code | meaning | example UI copy |
|-------------|---------|-----------------|
| `not_captured` | source never recorded this cell | "Projections not captured for 2017" |
| `pre_league` | predates 2010 | (excluded) |
| `unscored_season` | season not yet scored (data-driven on `is_scored`) | existing unscored-gap banner |
| `current_season_only` | source property (availability) | existing behavior |
| `source_gap` | known upstream hole (link the UP finding) | "Team-defense yards unavailable (upstream)" |
| `genuine_zero` | real 0, not a gap | render `0`, no affordance |

This replaces scattered, per-feature gap logic with one vocabulary the `DataGap` primitive consumes.

### 4. Where it lives

- **BFF:** grow `analytics/coverage.py` into the matrix (or add `analytics/coverage_matrix.py`
  importing the relevance helpers). Keep it pure `rows → structure`, tested. Reuse
  `played_season_ids`, the `is_scored` flag, and the workstream-1 canonical-identity helper.
- **API:** extend `/v1/meta` or add `/v1/meta/coverage` returning the matrix (relevance summary +
  per-feed/per-season coverage with reason codes). New pydantic schema → `npm run gen:api` + drift
  check; never hand-edit the client.
- **Repository (`../danger-zone/queries.py`):** add read-only helpers only if a needed scan isn't
  expressible through existing repository reads (e.g., a cluster-aware league-relevant player set).
- **Frontend:** drive the `DataGap` affordance from the coverage payload so empties explain
  themselves; optionally a small `/coverage` debug/admin view rendering the matrix for QA. **No
  math in `web/`** — it only reads `present/absent/reason`.

### 5. First consumer — close the originating bug

Wire the matrix into the box score (`analytics/matchups.py` / `BoxScorePage.tsx`): when
`projections` coverage is `absent` for the season/week, the Proj/Value columns render an explicit
"projections not captured for {season}" affordance (or are suppressed for that season with a
note), instead of a column of bare `—`. Prove it on `/matchups/1823/` (2017 W7) and on a covered
cell (a 2025 W1 box score) — the matrix-driven behavior must be correct on both.

---

## Tests (this is the durability — without it, the matrix rots like everything else did)

1. **Coverage contract test (known-answer, fixture DB):** assert the measured truth above —
   projections present only for {2024,2025,2026}×W1; scored 2010–2025; injuries include 2009 in raw
   but **excluded** by relevance; etc. This test **fails when coverage silently changes**, which is
   the signal that was missing. (See memory `phase2-conventions` — fixture-DB known answers.)
2. **Relevance regression test:** no non-league player / pre-2010 row appears in any league-scoped
   index; the exclusion tallies match expected counts (±documented drift).
3. **Identity-cluster relevance test:** a stranded stats-twin (e.g. Mike Williams 25239) is counted
   *relevant* via its rostered cluster-mate (1032), not excluded as "never rostered."
4. **Box-score gap test:** 2017 W7 → projections cell `absent`/`not_captured` and the UI renders the
   explanatory affordance, not `—`; 2025 W1 → `present` and values render.

## Done when

- `/v1/meta/coverage` returns a data-driven relevance + coverage matrix with reason codes; computed
  from the DB (no hardcoded years); identity-cluster-aware relevance.
- The `DataGap` affordance is driven by it; the originating bug (`/matchups/1823/` Proj/Value)
  renders a self-explaining gap; a covered cell still renders values.
- All four tests green; full green gate green; click-through done on both a covered and an
  uncovered matchup.
- The anti-whack-a-mole principle is written into `docs/08_TESTING_STRATEGY.md`; `docs/03_DATA_ACCESS.md`
  gap table points at the matrix as the source of truth; `PROGRESS.md` + `docs/ACTIVE_WORK.md`
  updated; memory `pre-2016-reconstruction-path` / a new coverage memory noted.
