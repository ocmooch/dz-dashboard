# Plan — Players view audit & remediation (dz-dashboard side)

**Scope:** the `/players` index + `/players/:id` detail (`web/src/features/players/*`),
`analytics/players.py`, `api/routes/players.py`, and the player-facing schemas.
**Companion:** `docs/handoffs/players-audit-danger-zone.md` (the DB-side fixes this plan
assumes will land). This plan is sequenced so the dashboard improves **with or without**
the DB work, and lights up fully once the DB fixes land.

## Problem restated

The `/players` index is the entire nflverse player universe (3093), not the league's
players. Only **1244** were ever league-rostered; **879** were never rostered and never
scored (pure noise), many flagged `is_active=1` with a stale current `nfl_team`. Detail
pages show `—` for rookie year and have **no "last year played"** field at all
(`last_season` is NULL in the DB *and* absent from `PlayerOut`). The index gives no signal
about which entries are trustworthy, so users land on dead/irrelevant players first.

This violates two house rules: **"never render 0/empty for missing data — use the gap
affordance"** and the index's job of surfacing *insights*, not noise.

## Design principles for this work

- **No metric/business math in `web/`.** "League relevance," sorting, and gap reasons are
  decided in `analytics/` (Python) and the repository, not the SPA.
- **Honest gaps, never fake values.** A missing rookie year stays `—`/DataGap; we do not
  invent it. The fix is to *populate the source* (DB handoff) and *stop showing noise*.
- **Don't hand-edit the generated client.** Any schema change → BFF schema + `gen:api`.
- The dashboard cannot change `is_active`, `last_season`, or roster correctness — those are
  DB-side. The dashboard's lever is **what it queries, how it scopes, and how it labels.**

## Phase A — dashboard-only, ships before DB fixes

These need **no** danger-zone change; they make the index trustworthy immediately by
scoping to league relevance and labeling the rest.

### A1. Scope the index to league-relevant players (default on)

The index should default to players who actually matter to this league — those ever on a
`team_rosters` row (optionally OR ever scored). Implement the *decision* in a new
read-only repository helper rather than joining in the route or the SPA.

- **Preferred:** add to danger-zone `search_players(..., league_relevant: bool | None)` —
  but that's a Phase-1 query change. Per CLAUDE.md, additive read-only helpers in
  `ff_pipeline/repository/queries.py` are *allowed*; fold this into the handoff (it's
  listed there as D4 option (a)). Until it lands:
- **Dashboard-side bridge (allowed, no math in web):** add `analytics/players.py:
  list_player_index(session, filters)` that calls the existing repo helpers and filters to
  rostered/scored players using repository reads only (e.g. a `players_ever_rostered()`
  id-set helper added to queries.py — additive, read-only). Route `/v1/players` calls this
  instead of raw `search_players`. The SPA still does zero logic.
- Add a query param `scope=league|all` (default `league`) so the full nflverse universe is
  still reachable but not the default. Surface it in the UI as a toggle
  ("League players · All NFL players").

**Done when:** default `/v1/players` returns only league-relevant players (≈1244, not
3093); `scope=all` returns the full set; the SPA toggle drives the param; analytics is
tested against the fixture DB with a known relevant/irrelevant pair.

### A2. Enrich the index row so a user can judge relevance at a glance

Right now a row is `name · pos · NFL`. Add columns the analytics layer can compute from
existing data without DB changes:

- **Seasons rostered** (e.g. "2012–2018") from `team_rosters` — answers "is this a real
  league player?" Far more honest than the `active/retired` badge.
- **Scored?** a small marker when the player has ≥1 scored row (so "zero stats" players are
  visibly flagged, not silently listed).

Add these to `PlayerLite`/the index payload via the BFF schema (dashboard-owned
`PlayerIndex` row model, not the Phase-1 `PlayerLite`), wire through `analytics/players.py`,
regenerate the client. **Do not** compute the range in the SPA.

**Done when:** each index row shows a rostered-seasons span and a scored marker; both come
from analytics; `npm run gen:api` drift check is clean.

### A3. Replace the `active/retired` badge with something true

`is_active` is unreliable (478 league-rostered players flagged active are years stale; the
crawler's `status is None → True` makes unknowns active). Until the DB clarifies semantics
(handoff D3):

- On the **detail page**, stop leading with the active/retired badge. Show **"Rostered
  YYYY–YYYY"** (from ownership) as the primary status line. Keep `is_active` only as a
  muted, clearly-sourced "NFL status (nflverse)" line, or drop it until D3 lands.
- On the **index filter**, relabel the `active` filter or hide it until D3; an
  "active/retired" filter that's wrong is worse than none.

**Done when:** no prominent UI element asserts active/retired off the unreliable flag;
rostered-span is the primary status; the misleading filter is gone or clearly hedged.

### A4. Detail page: honest gaps for missing biographical fields

`rookie_year`/`birth_date` already fall back to `—`. Leave the value honest, but when
rookie year is missing render the `DataGap` affordance (`reason="player_bio_unavailable"`)
rather than a bare `—`, consistent with the rest of the app. Add the reason label to
`DataGap` in `design-system/index.tsx`.

**Done when:** missing bio fields use the gap affordance, not a bare dash; new reason
labeled.

### A5. Ownership timeline: collapse week-by-week into ownership *spans*

The timeline currently lists every (season, week) roster row, so a season-long hold reads
as ~17 near-identical rows — which *looks* like the player bounced between owners. Collapse
consecutive same-team weeks into a span ("Team X · 2018 wk3–wk17 · draft") in
`analytics/players.py:ownership_timeline`. This also makes any *genuine* mid-season owner
change legible instead of buried. (Pure presentation collapse is a metric → compute in
Python, not the SPA.)

**Done when:** ownership renders as spans; a fixture player rostered all season shows one
span, not N rows; a traded player shows two spans.

## Phase B — lights up once DB fixes land (handoff D1–D5)

Gated on danger-zone work; mostly wiring + removing the Phase-A hedges.

### B1. Surface "Last year played" (gated on D1 + `PlayerOut.last_season`)

Once `last_season` is populated and added to `PlayerOut`: regenerate the client, add a
**"Last year played"** stat next to "Rookie year" on the detail page
(`PlayerDetailPage.tsx` bio card). Keep `—`/DataGap when still NULL (true source gap).

**Done when:** detail page shows last-year-played from `last_season`; gen:api drift clean;
NULL still renders a gap, not 0.

### B2. Restore a trustworthy active/retired signal (gated on D3)

Once `is_active` has documented stable semantics (or a derived league-relevance field
lands), reinstate the badge/filter using the corrected source and remove the A3 hedge.

### B3. Fold league-relevance scope onto the DB helper (gated on D4)

If D4 lands the `league_relevant` param (or `first/last_rostered_season` columns), retire
the dashboard-side id-set bridge from A1 in favor of the repository filter, and show the
rostered span from the DB column instead of computing it.

### B4. Drop the contamination guard's noise (gated on D5)

After D5 cleans duplicate roster rows, confirm the `matchups.py` home/away shared-player
guard no longer fires on real data (keep the guard as defense-in-depth). No code change
expected unless the guard is currently masking rows we'd rather surface.

## Files that will be touched

- `src/ff_dashboard/analytics/players.py` — index scoping (A1), row enrichment (A2),
  ownership spans (A5)
- `src/ff_dashboard/api/routes/players.py` — `scope` param, enriched index payload
- `src/ff_dashboard/api/schemas.py` — dashboard-owned enriched index row; later `last_season`
- `ff_pipeline/repository/queries.py` — **additive read-only** `players_ever_rostered()` /
  optional `league_relevant` (coordinate via handoff; allowed by CLAUDE.md)
- `web/src/features/players/PlayersPage.tsx` — scope toggle, new columns, filter relabel
- `web/src/features/players/PlayerDetailPage.tsx` — rostered-span status, last-year-played,
  bio gap affordance
- `web/src/design-system/index.tsx` — new `DataGap` reason label(s)
- `tests/dashboard/test_players.py` (+ `web/.../players.test.tsx`) — fixture-DB known
  answers for relevance scoping, ownership spans

## Test list (fixture DB, known answers)

- `list_player_index` default excludes a never-rostered fixture player; `scope=all`
  includes it.
- Index row exposes correct rostered-season span + scored marker for a known player.
- `ownership_timeline` collapses a full-season hold to one span; a traded player to two.
- Missing-rookie-year fixture player → gap reason, never `0`/empty.
- (B-phase) `last_season` renders when present, gap when NULL.

## Done when (overall)

- The default `/players` index shows league-relevant players only, each row legible enough
  to judge relevance; the full universe is opt-in, never the default.
- No UI element renders a fabricated or unreliable assertion (no fake 0s, no
  trust-the-broken-`is_active` badge); every gap uses the affordance.
- Ownership reads as spans, not week spam.
- Phase-B items either shipped (DB fixes landed) or tracked as gated, with the Phase-A
  hedges still honest in the meantime.
- Green gate (backend pytest+ruff+mypy; frontend gen:api drift + typecheck+lint+test);
  clicked through `/players` and two detail pages (one rich, one sparse/never-rostered).
- `PROGRESS.md` updated; committed with the trailer format.
