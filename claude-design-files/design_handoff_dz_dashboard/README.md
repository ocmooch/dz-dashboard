# Handoff: Danger Zone — League Analytics Dashboard

## Overview
"Danger Zone" is a read-only analytics dashboard for a long-running fantasy football league
(16 seasons of history, 10 fully scored). It surfaces league standings, weekly matchups,
all-time records, and — most importantly — **computed owner insights and head-to-head
rivalries** that you cannot get from the raw platform (Sleeper/NFL.com). The product's
point of difference is *analysis*: trends, strengths/weaknesses, and rivalry narratives
derived server-side from historical performance.

Two backend repos feed this (referenced by the stakeholder, not included here):
- `ocmooch/danger-zone` — data pipeline / scoring engine (produces the scored seasons + "run #N").
- `ocmooch/dz-dashboard` (branch `dev`) — dashboard BFF / API layer.

The frontend is expected to be **read-only** over whatever those services expose. Every
metric is precomputed; the UI never writes.

## About the Design Files
The files in this bundle are **design references created in HTML/CSS/vanilla JS** — a
working prototype that demonstrates the intended look, layout, and interaction model. They
are **not** production code to copy verbatim. Your task is to **recreate these designs in
the target codebase** (`dz-dashboard` appears to be the frontend home) using its established
framework, component library, data-fetching, and routing patterns. If no frontend framework
is established yet, React (with a charting lib such as Recharts/visx for the bump chart and
a plain CSS-grid heatmap) is a clean fit — the prototype is deliberately framework-agnostic
so it ports directly to JSX.

Treat the vanilla-JS data generation in `app.js` (the `buildSeries`/`h2h`/`heatColor`
functions) as a **spec for the shape of data and the derived metrics you need from the API**,
not as logic to ship. In production these numbers come from the backend.

## Fidelity
**High-fidelity.** Final colors, typography, spacing, and interaction states are all
specified here and in `styles/tokens.css`. Recreate the UI pixel-faithfully using the
codebase's libraries. The **Wireframe mode** inside the prototype is the only lo-fi part —
it exists to communicate IA/layout for surfaces not yet built to hi-fi (Standings) and
should be treated as structural guidance, not final visuals.

> Note: the prototype ships a top "design-system selector" rail (Mode: Frontend/Wireframe,
> Surface picker). **That rail is a presentation harness for reviewing the design — it is NOT
> part of the product.** Do not build it. The real app's navigation is the left sidebar.

---

## Surfaces / Views

### 1. Command Center (Home) — hi-fi
**Purpose:** One-glance league pulse. Answers "what's the state of the league right now?"

**Layout:** App shell = sticky top bar (72px) + sticky left nav (232px) + main content
(max-width 1320px, padding 32px 48px). Main is a vertical stack (`gap: 32px`):
1. **Page header** — eyebrow "COMMAND CENTER", H1 "THE DANGER ZONE", lede paragraph.
2. **Stat strip** — 4-up `statgrid` (Seasons / Scored Era / Season Leader / Champion). 1px hairline gaps, shared rounded container.
3. **Owner Signal** (signature element) — full-width `insight` card. Left: avatar + PF-trajectory sparkline. Right: headline with accent-colored owner name, detail sentence with inline mono stats, and a row of trait chips (good=green `▲`, bad=red `▼`, neutral). This is the auto-surfaced "what makes this owner unique" moment — the product's hero differentiator.
4. **Standings (top 6) + Week matchups** — 2-col grid (1.35fr / 1fr). Standings is a `tbl` (rank, manager chip, W–L record, PF, streak pill). Matchups card lists rows with two owner sides, scores, and a FINAL/LIVE pill.
5. **Power Movers + Rivalry of the Week** — 2-col grid (1fr/1fr). Movers = ranked list with sparkline + ▲/▼ delta. Rivalry = series tally (11–7) + mini heat preview, teasing the Rivalries surface.
6. **Records Book** — 4-up `rec-grid` (highest score, best player week, most titles, longest streak). The 4th cell shows a **DataGap** badge instead of a fake number.
7. **Footnote** — coverage disclosure with a DataGap chip.

### 2. Rivalries — hi-fi
**Purpose:** The emotional payload of a 16-year league. Owner-vs-owner history, made explorable.

**Layout:** Page header + vertical stack:
1. **Insight strip** — 4-up statgrid: Most-played rivalry, Closest by margin, Most lopsided, Hottest active streak. These are *computed* league-wide superlatives.
2. **Two-column body** (1.5fr / 1fr):
   - **Win-Pct Matrix** (left) — N×N heatmap. Rows/cols = owners. Cell = **row owner's win-pct vs column owner**, 0–100, background heat-colored (red→steel→green via `heatColor`). Diagonal = inert. Never-met / pre-2016 pairs = **hatched DataGap cell showing "—", never 0**. Cells are clickable + keyboard-focusable; selected cell gets an accent outline + glow. Legend ramp in the card header.
   - **Head-to-Head panel** (right) — updates on cell click. Shows both owner avatars, big series tally (green/red), 4 stat cells (Meetings, Avg margin, win-pct, longest streak), an auto-generated narrative insight sentence, and a recent-meetings log (season·week, W/L tag, who-beat-who, signed margin). Pre-2016 DataGap footnote.

### 3. Standings — wireframe only (lo-fi)
Structure to build to hi-fi later: sortable sticky-header table (through-week stepper) +
a rank-over-time **bump chart** (one line per owner, week-by-week). Mobile: table →
horizontal scroll with sticky first column.

---

## Interactions & Behavior
- **Left nav** switches surfaces (Home ↔ Rivalries). Active item has an accent left-bar + glow and `aria-current` semantics. Items marked "soon" (Teams, Players, Draft) are disabled placeholders.
- **Matrix cell**: click OR Enter/Space → renders that pairing in the H2H panel and moves the selection outline. Hover scales the cell 1.08 + shadow.
- **Standings header**: clicking a `th` moves the sort caret (prototype is visual only; wire to real sort).
- **Season switcher** (top bar `<select>`): scopes the data. Options include a live season ("2025 · live") and unscored seasons ("2015 · not scored") — unscored seasons must surface DataGaps, not blanks.
- **Data status** (top bar): live dot + "Data as of <date> · run #N" — reads from the pipeline's latest run metadata.
- No entrance animations (intentionally removed — keep it instant).
- `prefers-reduced-motion`: all transitions collapse to ~0ms.

## Honest Data Gaps (a first-class design pattern)
The single most important behavioral rule: **never fabricate a value for missing data.**
Coverage is partial (pre-2016 unscored, team-defense unscored, current season partial,
some owner pairs never met). Wherever a metric can't be honestly computed, render the
`.datagap` affordance — a dashed-border, hatched chip with a small amber diamond and a
plain-language reason ("Not scored · pre-2016", "never met"). It appears in: records cells,
matrix cells, H2H footnotes, and the home footnote. Quiet but unmistakable. Build this as a
reusable `<DataGap reason="…" />` component.

## State Management
- `currentSurface` (home | rivalries | …) — drives nav + routing. Recommend real routes (`/`, `/rivalries`).
- `season` — selected season scope; refetches surface data.
- `selectedPair` ({rowOwnerId, colOwnerId}) — Rivalries; drives the H2H panel. Default to the league's featured/closest rivalry.
- Data fetching: each surface loads precomputed aggregates from the BFF. Suggested shapes:
  - `GET /standings?season=` → `[{ rank, ownerId, name, w, l, t, pf, pa, streak }]`
  - `GET /matchups?season=&week=` → `[{ home, away, homeScore, awayScore, status }]`
  - `GET /owners/insights?season=` → `[{ ownerId, headline, detail, traits:[{label,kind}], sparkline:[…] }]`
  - `GET /rivalries/matrix?` → `{ owners:[…], cells:[[{ pct, wins, losses, met:boolean }]] }`
  - `GET /rivalries/:a/:b` → `{ total, aWins, bWins, avgMargin, longestStreak, games:[{season,week,winner,margin}] }`
  - `GET /records` → all-time superlatives, each with an optional `gap` reason.
  - `GET /meta` → `{ dataAsOf, runNumber, seasonsTotal, seasonsScored, coverageNotes }`
- The derived helpers in `app.js` (win-pct, heat color, longest streak, narrative sentence) document exactly which derived fields the UI expects — compute these server-side.

## Design Tokens
All tokens live in `styles/tokens.css` under `[data-direction="afterburner"]` (the dark HUD
theme — the only theme being shipped). Key values:

**Color**
- Background `#0b0e13` · Surface-1 `#12161d` · Surface-2 `#1a2029`
- Border `#262d38` · Border-strong `#36404e` · Hairline `#1f2630`
- Text `#e7ecf3` · Muted `#9aa7b8` · Faint `#5f6b7c`
- Accent (orange, emphasis/live) `#ff6a1a` · Win `#34d39e` · Loss `#ef4761` · Warn `#f5b73d` · Info `#5aa9ff`
- Categorical ramp: `#ff6a1a #5aa9ff #34d39e #f5b73d #b07cff #ff8fa3`
- Heatmap interpolation: loss `rgb(239,71,97)` → steel `rgb(57,65,78)` → win `rgb(52,211,158)`

**Typography**
- Display (titles, big numbers): **Saira Condensed** 600/700, uppercase, tight letter-spacing. Jersey-number energy.
- Body: **IBM Plex Sans** 400–700.
- Mono (ALL numbers — tabular): **IBM Plex Mono**, `font-variant-numeric: tabular-nums`, `font-feature-settings: "tnum" 1, "zero" 1`.
- Numbers must always be mono + tabular so columns align.

**Spacing** (8px base): 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 → `--s1`…`--s8`.
**Radius:** 6 / 10 / 14 (`--radius-sm` / `--radius` / `--radius-lg`).
**Shadows:** panels use `--panel-shadow` (inset top highlight + soft drop). Accent glow `--glow-accent` for live/selected.
**Layout:** max content width 1320px · nav 232px · top bar 72px.

**Theme caveat (important for whoever previews this):** the prototype declares
`color-scheme`. The original concept had a second light "Blueprint" theme; it was dropped
per stakeholder — ship the dark Afterburner theme only.

## Components to build (reusable)
`Card` (head + body), `Stat`/`StatGrid`, `Table`, `Chip`+`Avatar`, `Pill` (win/loss/accent),
`RecordLine` (colored W–L), `DataGap`, `Sparkline`, `Matchup` row, `Mover` row,
`RivalryMatrix` (heatmap grid), `H2HPanel`, `BumpChart` (standings, not yet built).

## Assets
- **Fonts:** Saira Condensed, IBM Plex Sans, IBM Plex Mono — Google Fonts (swap to self-hosted in prod).
- **Icons:** currently Unicode glyphs (▦ ▤ ⚔ ◍ ⇄ ★). Replace with the codebase's icon set (Lucide/Heroicons or similar).
- **Avatars:** 2-letter monograms. Swap for real owner avatars if available.
- No raster image assets in this design.

## Files in this bundle
- `Danger Zone Dashboard.html` — full prototype (Home + Rivalries hi-fi, Wireframe mode). Open in a browser to interact.
- `styles/tokens.css` — design tokens (the source of truth for color/type/space).
- `styles/app.css` — shell + Home + shared component styles.
- `styles/rivalries.css` — Rivalries surface (matrix + H2H panel).
- `styles/wireframe.css` — lo-fi wireframe styling (reference only; not for production).
- `app.js` — surface switching + Rivalries data/derivation. **Read the rivalry math as a data spec; the real numbers come from the backend.**

## Out of scope / do not build
- The top "design-system selector" rail (review harness only).
- Wireframe mode (communication artifact).
- The dropped light "Blueprint" theme.
- Any write/edit functionality — this product is read-only.
