# Design Handoff — dz-dashboard

A handoff brief for iterating dashboard design options (e.g. in a UX/UI design
tool) on **dz-dashboard** as the visual extension of **ff-pipeline**. Pair this
with a screenshot of the dashboard as currently built and the two repo links
below. For the full rationale see `06_DESIGN_SYSTEM.md` and `07_PAGES_AND_VIEWS.md`.

## What this is

**dz-dashboard** is the web analytics dashboard for the **Danger Zone**, a
16-season fantasy-football league. It is the *visual layer* on top of
**ff-pipeline** (`~/danger-zone`), the data foundation that scores and stores 16
seasons of league history plus the live current season. Treat dz-dashboard as
**ff-pipeline made visible** — same league identity, same data, now explorable.

- **Repos:**
  - Dashboard: `github.com/ocmooch/dz-dashboard` (React + TS SPA in `web/`; read-only FastAPI BFF)
  - Data pipeline: `github.com/ocmooch/danger-zone` (`v1.0.0`)
- **Starting point:** the dashboard is built end-to-end (Home, Standings, Power,
  Matchups + Box score, Rivalries, Records, Players + detail, Stats, Draft,
  Coverage/About; manager pages are still placeholder stubs). It is a point to
  iterate on, **not a constraint to preserve**.

## What's wanted

Iterate **design options** for the dashboard. Deliver in two modes:

1. **Frontend design** — polished, production-grade visual comps (the real look-and-feel).
2. **Wireframe** — lower-fidelity structural layouts for IA/flow exploration.
3. *(Future, design for it now):* interactive prototype, and make the system
   **tweakable** — everything driven by tokens so the theme is swappable without a rewrite.

Give **a few distinct directions**, not one. One should faithfully execute the
established direction below; at least one should push somewhere fresh while
staying credible for a sports-data app.

## Established design direction (baseline to honor or deliberately depart from)

**"Danger Zone" — a dark, HUD/cockpit instrument-panel aesthetic.** Aviation /
afterburner motif: near-black instrument backgrounds, a single hot accent
(afterburner orange) used sparingly for emphasis and "live" state, warning-red
reserved for losses, cool steel for structure. Charts read like instrument gauges
/ HUD readouts, **not** generic pastel dashboards. Reference points the owner
named: **Sleeper** (modern, dense, dark, card-based) crossed with **NFL.com
fantasy** (dated but clean hierarchy, legible tables). Discipline: **refined, not
maximalist** — dense where data demands it, calm everywhere else. Avoid the
"default AI dashboard" look, Inter/Roboto, and purple-gradient-on-white.

**Tokens** (dark is default; design a light theme as a second token set behind `[data-theme]`):

- Surfaces: `--bg #0b0e13`, `--surface-1 #12161d`, `--surface-2 #1a2029`, `--border #262d38`
- Text: `--text #e7ecf3`, `--text-muted #9aa7b8`, `--text-faint #5f6b7c`
- Accents: `--accent #ff6a1a` (afterburner orange), `--win #34d39e`, `--loss #ef4761`, `--warn #f5b73d`, `--info #5aa9ff`
- Categorical ramp (color-blind-aware): `#ff6a1a #5aa9ff #34d39e #f5b73d #b07cff #ff8fa3`
- Type: a **characterful engineered display face** (not Inter) for titles + big
  numbers; legible body face; **IBM Plex Mono / tabular-nums for every score,
  record, and stat** so columns align.
- 8px spacing base; `--radius 10px`; subtle shadows; quick single-entrance motion
  (respect `prefers-reduced-motion`).

## Layout / IA

Persistent app shell, three zones:

- **Top bar:** DZ logo · global search (⌕ typeahead to any owner/team/player/season)
  · **global season switcher** · a **"data as of {date} · run #{id}"** indicator
  that opens a coverage panel.
- **Left nav** (collapses to bottom tab bar < 768px): Home · Standings · Matchups
  · Teams · Managers · Rivalries · Records · Players · Draft.
- **Main:** max-width container, cards on the instrument-panel background.
- **Primary target is laptop**; design the responsive collapse (tables →
  horizontal scroll with sticky first column).

## Core surfaces to design (priority order)

1. **Home — "Command Center":** standings snippet, this week's matchups,
   power-ranking movers, recent activity.
2. **Standings:** sortable table (rank, manager, W-L-T, PF, PA, streak) +
   standings-over-time rank/bump chart + "through week" stepper.
3. **Manager profile:** career header stats, **trophy case**, season-by-season
   table, trajectory chart.
4. **Rivalries:** N×N win-pct **heatmap matrix** → pairwise head-to-head page
   (high emotional value for a 16-yr league — make it shine).
5. **Records book:** superlative cards (highest score, biggest blowout, best
   player week, most titles…), each deep-linking to its source.
6. Box score, Team, Players index + detail, Draft board.

## Reusable component inventory

Design these as durable primitives; pages are disposable compositions of them.

`Button` · `Card` (header/body/footer) · `Stat` (big mono number + optional ▲/▼
delta) · `StatGrid` · `Badge`/`Pill` · `Table` (sortable, sticky header, hairline
borders not zebra, right-aligned mono numbers) · `Tabs` · `RecordLine` (W-L-T,
win/loss-colored) · `OwnerChip`/`PlayerChip`/`TeamChip` (avatar + name) ·
`Skeleton` · `EmptyState` · `ErrorState` · `Trophy` · `WeekStepper`, plus
**charts**: `LineTrend`, `BarCompare`, `StackedBreakdown`, `Heatmap`, `RankFlow`.

## Non-negotiables (these shape the UI, not just the backend)

- **Honesty about data gaps.** Unscored pre-2016 seasons, current-season-only
  availability, un-scored team defense, and never-met rivalries must render a
  dedicated **`DataGap`** affordance (a labeled badge, e.g. "Not scored — pre-2016
  season") — **never a fake `0`**. Design what this looks like; it appears throughout.
- **Every score/record/stat is monospaced + tabular** so numeric columns align.
- **Accessibility is baseline:** WCAG AA contrast (verify orange-on-dark and muted
  text), visible focus rings, non-color encodings on charts (direct labels),
  data-table fallbacks, semantic landmarks.
- **Token-driven and re-skinnable** — commit to one direction per option, but make
  the theme fully swappable via CSS variables.
