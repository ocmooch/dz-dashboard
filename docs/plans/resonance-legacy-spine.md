# Plan — Career Legacy-Spine (Resonance Leg, build #1)

Charter: `docs/PHASE2_5_RESONANCE.md`. First data-viz of the leg. Chosen because it is **pure
frontend on an existing payload** (fast richness, no `gen:api` drift) **and** it establishes the
**gold = champion / 💩 = Sacko marker grammar + reversed-rank axis** that later charts inherit.

## What it is

A manager's **career finish-position line across every season they played** — rank 1 pinned to
the top, championship seasons marked with a gold node, Sacko seasons with a 💩 node — plus a
one-line career caption ("Smokin Doubs · 2 titles · 1 Sacko · best 1st"). *One image = a career.*

This **supersedes the existing generic rank-trajectory chart** on the Manager Profile (which
plots `final_rank` as a plain `LineTrend` with no champion/Sacko context). We replace that chart
with the richer Legacy-Spine; we do **not** add a second rank chart.

## Why no backend

`GET /v1/owners/{owner_id}/seasons` → `OwnerSeasons.seasons: OwnerSeasonRow[]` already carries
everything needed per season: `season_year`, `final_rank` (nullable = gap, never 0),
`is_champion`, `is_sacko`, `result`. The Manager Profile already fetches this for its season
table, so the spine adds **no new request**. No analytics, no schema, no client regen.

> Contrast the existing `/trajectory` endpoint (`TrajectoryPoint`): it has `final_rank` but
> **not** `is_champion`/`is_sacko`, so it can't carry the markers. The spine reads from
> `/seasons` instead. (Leave `/trajectory` alone for now; a later cleanup can retire it if
> nothing else consumes it.)

## Files to touch

**New — the reusable primitive (the point of going first):**
- `web/src/charts/index.tsx` — add `export function LegacySpine({...})`. A reversed-Y rank line
  (rank 1 on top, domain `[1, teamCount-or-max]`), `final_rank === null` → a visible gap
  (no node, dashed bridge or break — never plotted as 0), with per-point node styling:
  champion → gold node, Sacko → 💩/brown node, else default. Same `ChartFrame` wrapper as the
  other charts (accessible title + `<details>` data-table fallback). Reuse `chartTheme`.
- Marker tokens: reuse existing champion/Sacko styling from `web/src/design-system/` if present
  (a `sacko` style already exists there); if no gold/champion token exists, add `--accent-gold`
  (and a Sacko brown) to `design-system/tokens.css` so the grammar is centralized for reuse.

**Changed — first consumer:**
- `web/src/features/managers/ManagerProfilePage.tsx` — replace the current rank-trajectory
  `LineTrend` with `LegacySpine`, fed from the already-fetched `/seasons` rows. Caption line from
  the `OwnerCareer` already on the page (`championships`, `sackos`, `best_finish`).

**Component signature (proposed):**
```ts
type LegacySpineSeason = {
  season_year: number | null;
  final_rank: number | null;   // null = gap (in-progress / rank-less) — render as a break
  is_champion: boolean;
  is_sacko: boolean;
};
function LegacySpine(props: {
  seasons: LegacySpineSeason[];
  fieldSize?: number;          // y-domain max; default = max rank seen, fallback 12
  title: string;
  height?: number;
}): React.ReactElement
```

## Visual grammar (establish here, reuse leg-wide)

- **Champion** → gold filled node (`--accent-gold`). **Sacko** → 💩 / brown node.
- Rank **1 on top** (reversed Y), integer ticks only.
- **Gaps are honest:** a null `final_rank` is a break in the line, not a 0 and not rank-last.
- Caption (in the page, not the chart): `{titles} title(s) · {sackos} Sacko(s) · best {ordinal}`.
  Suppress a clause at 0 ("0 titles" → omit), per the "never render 0 for missing/none" ethos.

## Tests (vitest component tests, the project's frontend norm)

`web/src/charts/` — new `LegacySpine` test:
1. Renders one node per season with a non-null rank; reversed axis (rank 1 visually top).
2. Champion season carries the gold marker class/role; Sacko season carries the 💩 marker.
3. A null `final_rank` produces a gap (no node at 0; line breaks) — assert no `0` data point.
4. The `<details>` data-table fallback lists each season's year + result.

`ManagerProfilePage.test.tsx` — update: the profile renders `LegacySpine` (not the old rank
`LineTrend`); a known fixture owner with a title + a Sacko shows both markers and the caption.

## Done when

- `LegacySpine` exists in `web/src/charts/`, themed, with the data-table fallback; champion/Sacko
  markers and reversed-rank axis render; gaps are breaks, never 0.
- Manager Profile shows the spine in place of the old rank trajectory, with the career caption.
- Frontend gate green: `npm run typecheck && npm run lint && npm run test`; **`gen:api` drift
  check unchanged** (no backend touch). No new fetch added to the page.
- Click-through: open a multi-title manager (e.g. a known champion) and a Sacko-holder; the gold
  and 💩 nodes land on the right seasons; a manager with an in-progress/rank-less season shows a
  gap, not a bottom-rank dot.

## Out of scope (follow-ups, noted not built)

- **Legacies Wall** — a small-multiples grid of every manager's spine on the Managers index.
  Wants all owners' per-season finishes at once; the career list only carries `trophy_case`
  (champ/Sacko years), not full finishes — so the wall needs either N `/seasons` calls or a new
  aggregate endpoint. Separate plan; do **not** pull it into this build.
- Animation, era-band shading behind the spine — later grammar polish.
