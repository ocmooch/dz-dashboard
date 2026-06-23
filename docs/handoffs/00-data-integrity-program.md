# Handoff → Data Integrity & Coverage Program (START HERE)

**Status (2026-06-16):** ◐ in progress — re-cut into 5 single-repo units; **live cycle-state is
tracked in `docs/ACTIVE_WORK.md` §0, not here.** This file is now reference framing only (its one
build deliverable — the anti-whack-a-mole rule in `docs/08_TESTING_STRATEGY.md` — is ☑ done).
· **Owns:** the two recurring, cross-cutting data problems behind
most "it works here but not there" reports · **Scope:** spans both repos (`dz-dashboard` Phase 2
+ `../danger-zone` Phase 1) · **Authored:** 2026-06-16, against the live DB
(`../danger-zone/data/fantasy.db`).

This is the coordinator. Read it, then run the two workstream handoffs it points to. It is the
"why" and the order; the workstream files are the "what" and the "done when."

---

## Why this program exists (the mental model — do not skip)

The dashboard is a **faithful renderer sitting on top of an unevenly-populated, partly-fractured
data substrate.** It does no math (hard rule: no metric math in `web/`), and it never renders `0`
for missing data (hard rule: use the `DataGap` affordance). Both rules are correct. Their
combined consequence is the thing that *feels* like whack-a-mole:

1. **Coverage is uneven cell-by-cell** (season × week × player × feed). Projections exist only for
   week 1 of 2024–2026. Injury reports run 2009–2025. Scored stats 2010–2025. A feature validated
   on the current season's week-1 box score looks complete and is silently empty everywhere else.
2. **Identity is fractured.** The same real player can exist as two `player_id` rows — one from
   NFL.com (`nfl_com_player_id`), one from nflverse (`gsis_id`) — with the roster pointing at one
   and the stats/injuries living under the other. The renderer faithfully shows the empty one.
3. **The gap rule turns both into *silent absence*, not errors.** Nothing throws. You only find a
   gap by navigating to it. So you cannot tell a data-gated feature is "done" by looking at one
   page — only that it works *on that page*. The next page exposes the next unevenness, and the
   cycle repeats.

The fixes shipped so far (matchup context, played-guard, DATA-flag cleanup — PRs #73/#74/#75) are
all real and all correct. But each patched **one observed cell**. None was anchored to a map of
*which cells have which data* or to a *canonical identity*. This program builds those two anchors
so future work can be characterized as whole, not eyeballed one page at a time.

### The worked example that motivated this (keep as the canonical reproduction)

`/matchups/1823/` = **2017 week 7**. Two symptoms, one substrate:

- **Proj / Value columns blank.** The `projections` table has rows only for week 1 of 2024, 2025,
  2026 (and only 2025 carries `projected_points`). 2017 W7 was never captured → every row renders
  `—`. Not a regression — the feature never had coverage outside that slice.
- **"Mike Williams" shows DNP with no injury status.** The 2017 roster references player_id
  **1032** (NFL.com identity, `nfl_com_player_id=2558846`, no `gsis_id`, no scored rows, no injury
  rows). The *same real player's* stats and injuries live under player_id **25239** (nflverse
  identity, `gsis_id=00-0033536`: W7 = 0.0 scored, and an "Out (Back)" injury history weeks 1–6).
  The box score looks up 1032 → no stat line → `classify_zero` → DNP; → no injury → no badge. The
  data exists; it's just under the twin the roster doesn't point at.

Both are the program in miniature: a coverage gap and an identity split, each rendered honestly,
each invisible until navigated to.

---

## The two workstreams (run in this order)

### 1. Player Identity Resolution → `player-identity-resolution.md`
Stamp out the `player_id` confusion permanently. Canonical fix is upstream (danger-zone): cluster
the cross-source duplicate records to one canonical identity and make ingestion identity-aware so
new loads attach to the right player instead of minting a twin. Dashboard side: consume the clean
identity and, until it lands, **detect and report** splits (feeding the matrix below) rather than
inventing reconciliation math.

**Why first:** the coverage matrix's relevance scope is *identity-cluster-aware*. A naive "is this
player_id rostered?" filter would correctly mark 1032 relevant and **wrongly exclude 25239** — the
very record holding the data. Relevance must be evaluated over resolved identity clusters, so
identity resolution is a prerequisite for an honest matrix. Extends open finding **F-25**
(`docs/ACTIVE_WORK.md` §2) and the prior `docs/handoffs/players-audit-danger-zone.md`.

### 2. Data Coverage & Relevance Matrix → `data-coverage-matrix.md` (PARAMOUNT)
The single, data-driven source of truth for **which entities are relevant to this league** and
**which feeds have data for which season/week**. It instructs both the DB layer (whether to even
attempt a field) and the UI (gap affordances that *explain themselves*: "Projections not captured
for 2017" instead of a bare `—`). It is built by extending the existing `analytics/coverage.py`
(today only a thin `/v1/meta` summary) into a full, tested matrix, with an explicit, auditable
**relevance boundary** so the legacy-era leakage (3,000 non-league players, pre-2010 injury rows)
is filtered *visibly*, not silently.

---

## The durable principle this program installs (the anti-whack-a-mole rule)

After this lands, the standard for any data-gated feature becomes:

> **A feature is not "done" when it works on the page in front of you. It is done when it declares
> its coverage envelope from the matrix and renders a self-explaining gap everywhere outside it.**

Codify this in `docs/08_TESTING_STRATEGY.md` and enforce it with the matrix **contract tests**
(known-answer assertions that fail when coverage silently changes) defined in workstream 2. That
test is what converts "silent absence" back into "a signal" — the missing piece that let these
issues hide.

---

## Cross-repo boundary (non-negotiable)

- **dz-dashboard is read-only on the DB.** No INSERT/UPDATE/DELETE; the identity *merge* and any
  backfill happen in `../danger-zone`. The dashboard consumes the result and may add read-only
  helpers in `ff_pipeline/repository/queries.py` only.
- **Contract changes flow through the schema, never the client.** Any new `/v1/meta/coverage`
  shape or new `PlayerOut` field is added to the BFF pydantic schema, then `npm run gen:api` +
  the drift check — never hand-edit `web/src/lib/api/`.
- Sequence danger-zone and dashboard PRs so each dashboard `gen:api` drift check runs against the
  schema it depends on, in the same cycle.

## Definition of done (whole program)

- Identity: zero league-rostered players whose stats/injuries are stranded under an unmerged twin;
  ingestion is identity-aware; the dashboard reads a canonical identity (or a documented crosswalk).
- Matrix: `/v1/meta/coverage` returns a data-driven, identity-cluster-aware relevance + coverage
  map; the UI's `DataGap` affordance is driven by it and explains *why* a cell is empty; contract
  tests pin the current coverage truth and the relevance boundary; no non-league entity appears in
  any league-scoped index (regression-tested).
- `docs/ACTIVE_WORK.md`, `PROGRESS.md`, and the relevant memories updated; the principle above is
  written into `docs/08_TESTING_STRATEGY.md`.
