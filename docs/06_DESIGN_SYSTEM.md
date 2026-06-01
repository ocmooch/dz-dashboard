# 06 — Design System & UX

This document defines the visual and interaction language so that components are built once,
well, and reused everywhere — making later polish additive rather than a rewrite (N3.2). It
takes inspiration from two reference points the user named: **Sleeper** (modern, dense,
card-based, dark, fast) and **NFL.com fantasy** (dated but clean, clear hierarchy, legible
tables). The goal is the best of both: Sleeper's polish with NFL.com's clarity.

## Aesthetic direction (proposed — confirm in `10_OPEN_QUESTIONS.md` Q3)

**"Danger Zone" — a dark, HUD-inspired cockpit for league data.** The league's identity
(repo `danger-zone`, ruleset `dz-rules.csv`) is the hook. Lean into a restrained
aviation/afterburner motif: near-black instrument-panel backgrounds, a single hot accent
(afterburner orange) used sparingly for emphasis and "live" state, warning-red reserved for
losses/negatives, cool steel for structure. Charts read like instrument gauges and HUD
readouts, not generic pastel dashboards. The discipline is **refined, not maximalist**:
dense where data demands it, calm everywhere else. This gives the app a memorable, coherent
character instead of the default "AI dashboard" look — and it's fully re-skinnable via tokens
if you'd rather go a different way.

> The skill guidance that matters here: commit to *one* clear direction and execute with
> precision; avoid generic fonts (Inter/Roboto/Arial) and the purple-gradient-on-white
> cliché; drive everything from CSS variables.

## Design tokens (CSS variables — the single source of theme truth)

Defined once in `design-system/tokens.css`; every component and chart reads from them. A
light theme is a second token set behind a `[data-theme]` attribute (dark is default).

```css
:root[data-theme="dark"] {
  /* Surfaces — instrument panel */
  --bg:            #0b0e13;   /* app background */
  --surface-1:     #12161d;   /* cards */
  --surface-2:     #1a2029;   /* raised / hover */
  --border:        #262d38;

  /* Text */
  --text:          #e7ecf3;
  --text-muted:    #9aa7b8;
  --text-faint:    #5f6b7c;

  /* Accents */
  --accent:        #ff6a1a;   /* afterburner orange — emphasis, live, primary CTA */
  --accent-quiet:  #ff6a1a26; /* 15% tint for fills */
  --win:           #34d39e;   /* positive / win */
  --loss:          #ef4761;   /* negative / loss */
  --warn:          #f5b73d;
  --info:          #5aa9ff;

  /* Data-viz categorical ramp (color-blind-aware, distinct in dark) */
  --series-1:#ff6a1a; --series-2:#5aa9ff; --series-3:#34d39e;
  --series-4:#f5b73d; --series-5:#b07cff; --series-6:#ff8fa3;

  /* Type scale (rem) */
  --fs-display: 2.25rem; --fs-h1: 1.75rem; --fs-h2: 1.375rem;
  --fs-h3: 1.125rem; --fs-body: 0.9375rem; --fs-sm: 0.8125rem; --fs-xs: 0.6875rem;

  /* Numbers want tabular alignment */
  --font-display: "Saira Condensed", "Arial Narrow", system-ui; /* as built — engineered display face, not Inter */
  --font-body:    "IBM Plex Sans", system-ui;
  --font-mono:    "IBM Plex Mono", ui-monospace;   /* all stats/scores use mono, tabular-nums */

  /* Spacing (8px base) */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-5:24px; --sp-6:32px; --sp-8:48px;

  /* Radius / shadow / motion */
  --radius:10px; --radius-sm:6px;
  --shadow-1:0 1px 2px #0008; --shadow-2:0 8px 24px #000a;
  --ease:cubic-bezier(.2,.7,.2,1); --dur-fast:120ms; --dur:200ms;
}
```

> Font note (as built): the display face is **Saira Condensed** (engineered/technical character
> for the HUD theme), the body face is **IBM Plex Sans**, and all numeric data renders in **IBM
> Plex Mono** with `font-variant-numeric: tabular-nums` so columns of scores align — never Inter.
> The token block above is illustrative; the **source of truth is `web/src/styles/tokens.css`**
> (which also adds `--accent-soft`/`--accent-line` helpers), so treat exact values there as
> canonical if they diverge from this snapshot.

## Typography rules

- Display face for page titles and big stat numbers only; body face for prose and labels.
- **Every score, record, and stat is mono + tabular.** Records like `12-9-1` and scores like
  `124.82` must align vertically in tables.
- Generous line-height for prose (1.5); tight for dense tables (1.25).

## Layout & navigation IA

A persistent **app shell** with three zones:

```
┌───────────────────────────────────────────────────────────────────────┐
│  TOP BAR:  [DZ logo]   ⌕ global search        [Season ▾ 2025]  data-as-of │
├───────────┬───────────────────────────────────────────────────────────┤
│  LEFT NAV │                                                             │
│  Home     │   PAGE CONTENT                                              │
│  Standings│   (max-width container; cards on the instrument-panel bg)   │
│  Matchups │                                                             │
│  Teams    │                                                             │
│  Managers │                                                             │
│  Rivalries│                                                             │
│  Records  │                                                             │
│  Players  │                                                             │
│  Draft    │                                                             │
└───────────┴───────────────────────────────────────────────────────────┘
```

- **Season switcher is global** and lives in the top bar; changing it re-points the current
  view (where the view is season-scoped) and is reflected in the URL.
- **Left nav** is the primary IA (collapses to a bottom tab bar / drawer on narrow screens).
- **Global search** (⌕) is a typeahead jumping to any owner/team/player/season.
- A small **"data as of {date} · run #{id}"** indicator sits in the top bar; clicking it opens
  a coverage panel (which seasons scored, reconstruction status, known gaps) sourced from
  `/v1/meta`.

## Core component inventory (`design-system/`)

Build these first; everything else composes from them.

| Component | Purpose / notes |
|-----------|-----------------|
| `Button` | primary (accent), secondary (steel), ghost; loading state |
| `Card` | the basic surface; header/body/footer slots |
| `Stat` | a big labeled number (mono, tabular); optional delta (▲/▼ in win/loss color) |
| `StatGrid` | responsive grid of `Stat`s for summary headers |
| `Badge` / `Pill` | status (win/loss, playoff, champion, live, "known gap") |
| `Table` | sortable, sticky header, zebra-off (use hairline borders), mono numeric cells, right-aligned numbers |
| `Tabs` | within-page section switching |
| `RecordLine` | renders `W-L-T` consistently with color emphasis |
| `OwnerChip` / `PlayerChip` / `TeamChip` | avatar + name, deep-links to the entity |
| `Skeleton` | loading placeholders matching final layout (prevents layout shift) |
| `EmptyState` | "nothing here yet" with optional action |
| `ErrorState` | error + retry (wired to TanStack Query retry) |
| `DataGap` | **the honesty component** — a labeled affordance ("not scored — 2010–2015", "team defense not scored", "availability current-season only") used wherever a metric is absent. Never render 0 in place of missing data. |
| `Trophy` | championship/podium marker for trophy cases |
| `WeekStepper` | prev/next week control bound to the URL |

## Charts (`charts/`)

Thin wrappers over Recharts, all reading `chartTheme.ts` (which reads the CSS tokens) so
charts match the theme and re-skin for free. Standard chart types:

| Wrapper | Used for |
|---------|----------|
| `LineTrend` | scoring trend, standings/power over time, player weekly scoring, owner trajectory |
| `BarCompare` | matchup team comparison, season totals, projection vs actual |
| `StackedBreakdown` | per-player point breakdown (passing/rushing/receiving/bonus) |
| `Heatmap` | rivalry matrix |
| `RankFlow` | standings-over-time as a bump/rank chart (one line per team) |

Chart rules:
- Always provide a non-color encoding too (labels, direct labeling) so meaning survives
  color-blindness; use the categorical ramp above.
- Tooltips show exact mono numbers; axes use abbreviated formats.
- Charts have accessible titles and a data-table fallback (a `<details>` with the raw
  numbers) for screen readers.
- Animate on first render only (staggered, brief); avoid constant motion.

## Interaction & motion

- One orchestrated entrance per page (staggered card reveal, ~200ms, `--ease`); route
  transitions are quick cross-fades. No gratuitous continuous animation.
- Hover raises a card to `--surface-2` with `--shadow-2`; focus rings use `--accent` and are
  always visible (never `outline:none` without a replacement).
- Optimistic, instant feel: render cached data immediately (TanStack Query), refresh in
  background, show a subtle "updating" shimmer only on the affected card.

## Responsive

- Primary target is a laptop (the user's main device). Layout is a max-width container with
  multi-column card grids.
- Below ~768px: left nav becomes a bottom tab bar; tables become horizontally scrollable with
  a sticky first column (owner/player name); multi-column grids collapse to one column.
- Charts get a minimum height and never overflow; very wide charts (rivalry matrix) scroll.

## Accessibility (baseline, not optional)

- Color contrast meets WCAG AA for text on every surface token (verify the orange-on-dark and
  muted-text combos).
- All interactive elements keyboard-reachable with visible focus.
- Charts carry text alternatives / data-table fallbacks.
- Respect `prefers-reduced-motion` (disable entrance animations).
- Semantic landmarks (`nav`, `main`, `header`) and labeled controls.

## Design principle, restated

Pick the components and tokens carefully now; treat pages as disposable compositions of those
durable parts. When you discover a view you wish existed, it should be assemblable from the
inventory above plus one new analytics endpoint — not a new design language.
