# Phase 2½ — The Resonance Leg

> *From archive to storyteller.* Provisional name; the concept is what matters.
> This is the strategic charter + backlog for the next leg of dz-dashboard. It is **not**
> Phase 3 (the "give a member a competitive edge" effort — see `PHASE3_DRAFT.md`). This leg
> stays squarely Phase 2: read-only, presentation-only, all math in `analytics/`.

Read this when orienting on *why* a new feature is worth building. Read `09_ROADMAP.md` for
the P0–P12 build history; read the per-build plan in `docs/plans/` for *how*.

> **This is a guide, not a cage.** The personas, the Relive/Reckon/Reveal jobs, the metric
> list, and the backlog are **scaffolding for generating ideas — not a closed taxonomy and not
> a must-build list.** An out-of-the-box idea that fits none of these categories is not out of
> scope; it's a signal to *expand the frame*, not to discard the idea. If a great feature
> doesn't map to a job, add a job. If a metric isn't in the table, build it. The only hard
> guardrails are the Phase 2 boundaries (read-only, presentation-only, math in `analytics/`)
> and the "not Phase 3 / no competitive edge" line. Everything else here is a prompt, not a
> permission slip — prefer the surprising idea over the catalogued one.

---

## Thesis

The dashboard has won on **correctness and completeness** — 35 analytics modules, honest gaps,
16 seasons reconstructed to the decimal. That is the **museum**: accurate, reverent, permanent.

What is thin is **resonance** — the emotional, narrative, and visual layer that turns a correct
record into a conversation. Note the gap is *not* "we have no charts": `web/src/charts/` already
ships solid theme-bound primitives — `LineTrend`, `BarCompare`, `StackedBreakdown`, `RankFlow`
(bump/rank chart), `Heatmap` (rivalry matrix), `ScatterQuadrant` (draft reach×outcome). The gap
is that they are **under-deployed and under-ambitious**: a handful of chart *types*, mostly one
per page, visualizing the metrics we happened to already compute. Missing are (a) **novel chart
types** the data deserves — distribution/beeswarm, streamgraph/area, a marked "legacy spine,"
zero-centered diverging bars — (b) the **resonant metrics** worth charting (most aren't computed
yet), and (c) a **consistent visual grammar** (gold = title, 💩 = Sacko, era bands) that makes
the charts a family. The data is a cathedral; the way it is *shown and felt* is a few plain
windows. That gap is the "something missing."

This leg builds the **barroom** next to the museum: provocative, ranked, opinionated, fun —
the part that makes a member screenshot a view into the group chat.

---

## Who this is for

Not "fantasy players." A **specific tribe of ~12–20 people** who have shared NFL seasons since
2010. The entire value is *particularity*: the same number is worthless with a stranger's name
and priceless with **Hamlin**, **Smokin Doubs**, the **Sacko**. Four real personas:

- **The active veteran** — wants bragging rights and rivalry ammo. *"Where do I rank all-time?
  Do I own this guy?"*
- **The departed alumnus** — the friendships outlasted the roster. Visits for nostalgia; wants
  their legacy **preserved**, not deprioritized into a footnote.
- **The lore-keeper / commissioner** — cares about the league as an institution: the canon, the
  continuity, the records.
- **The newcomer** — just joined; needs to learn whose ghosts they're playing against.

They are **not** strangers needing fantasy onboarding, and **not** competitors seeking an edge
(that's Phase 3). They come to **relive, reckon, and reveal.**

## The niche, in one line

**A museum *and* a barroom for one league's shared history.** Every future surface serves one
of three jobs:

- **Relive** — replay a famous game; feel a season as it happened; "remember when."
- **Reckon** — settle it. Who's the GOAT? Who owns whom? Who was carried by the schedule?
- **Reveal** — surprise a member with something about their *own* league they didn't know.

## The deepest gap: qualitative memory

The dashboard holds nearly all of the league's **quantitative** memory and almost none of its
**qualitative** memory. The real-life value of the Danger Zone is "long-lasting friendships,
make-believe rivalries, and drama" — none of which is on NFL.com. The dashboard can say a
rivalry is 14–11; it cannot say *why it matters* — the origin story, the trash talk, the
nickname, the season it turned personal. `curated_events.py` and `owner_story.py` exist but are
thin. The **league lore ledger** (below) is the one input only members can supply, and the thing
that turns every accurate number into a story.

---

## Design principles (the rules for this leg)

1. **Particular, not generic.** Every view should be impossible to mistake for any other
   league. The league's own vocabulary *is* the brand.
2. **Start a conversation.** Acceptance test: *would a member screenshot this into the group
   chat?* If not, it's museum, not barroom.
3. **Reverent to the record, playful in the telling.** Accuracy stays sacred; tone can be
   cheeky. Reframe gaps as *lore* ("the lost weeks of 2010"), not apologies.
4. **Every member is a protagonist** — including the departed. Alumni get preserved legacies.
5. **Show, then tell.** Lead with one image or number that lands instantly; detail unfolds on
   demand. Visual-first, drill-down-second.
6. **Time is the spine.** A 16-season institution's native grain is longitudinal — eras,
   trajectories, then-vs-now, anniversaries.

## North-star + the discovery engine

The meta-problem ("I struggle to find big-blast-radius ideas") comes from hunting for the next
*technical* improvement on a mature surface. Replace that with a **generative frame**:

> Stop asking "what's left to build?" Ask **"what would make a member feel something or say
> something?"**

Score every candidate by **resonance × reach ÷ effort**, file it under Relive / Reckon /
Reveal, and the backlog writes itself. Each build session picks the top unstarted card.

---

## The signature-metrics vocabulary (the fantasy-literate part)

Entire fantasy careers were built on inventing a *metric* — air yards, target share, targets
per route run, weighted opportunity (WOPR), snap share. They land because they **reveal a
hidden truth** the box score hides. In redraft, that truth is used to *predict* and *find an
edge* — which here is Phase 3. **This leg repurposes the same analytical spirit to reveal hidden
truths about people the members already know, and to settle arguments.** That is what makes the
charts non-generic: they are FF-native metrics, pointed at *our* league's history.

The league's own advanced-stats vocabulary. (`exists` = analytics already computes it;
`new` = a new `analytics/` module, but on data we already have.)

| Metric | FF lineage | What it reveals | Natural viz | Data |
|---|---|---|---|---|
| **Expected Wins (xW) / all-play record + Luck** | "schedule luck," all-play standings | Who's genuinely good vs carried/screwed by the schedule | Diverging bars (actual − expected) per season; career luck ledger | **exists** (`/standings/insights` → actual/expected/`luck_delta`/`all_play_win_pct` + most_robbed/blessed) |
| **Lineup Efficiency ("Manager IQ")** | "points left on the bench" as a skill signal | Who actually *manages* well, not just who scores | Efficiency leaderboard + per-manager trend; "bench regret" moments | exists (optimal lineup, `matchups.py`) |
| **Era-Adjusted Scoring (z-score / percentile)** | era adjustments, scoring inflation | Fair cross-era GOAT comparison (2010 ≠ 2025 scoring) | Normalized career scoring band | new (normalize existing) |
| **Volatility / Boom–Bust profile** | weekly consistency, ceiling/floor | The "scary" vs "steady" managers | Beeswarm/strip of weekly scores; ceiling–floor bars | exists (week-relative tendency profile) |
| **Clutch / close-game record** | situational splits | Who wins the games that matter | Record in <10-pt games; leverage | new (filter existing margins) |
| **Strength of Schedule faced** | SOS | Context that explains a record | SOS band per season | new |
| **Draft Capital Efficiency / Value-over-ADP** | ADP value, "draft heists" | Who drafts well vs who reaches | ADP-vs-points scatter, quadrant-labelled | exists (draft impact + ADP cushion) |
| **Transaction aggression / FAAB ROI** | in-season management, FAAB value | The wheeler-dealers; who turns $ into points | FAAB-spent vs points-added scatter; activity timeline | exists (FAAB + transactions) |
| **All-Play season standings** | round-robin "true power" table | A season's real strength order vs its record | Sortable table + delta-vs-record column | exists (`/standings/insights` `all_play_win_pct`) |
| **League Legends (most-rostered / most-points-for-us)** | usage/opportunity, but league-historical | The players who built *our* dynasties | Leaderboard + ownership timeline | mostly exists (players/rosters) |

**Keystone (already built):** the **all-play / Expected-Wins** metric — the single most beloved
"hidden truth" in fantasy — is *already computed* by `analytics/standings.py` and served at
`/v1/seasons/{id}/standings/insights` (`actual_wins`, `expected_wins`, `luck_delta`,
`all_play_win_pct`, `most_robbed`/`most_blessed`). So the high-value Luck visualization is a
**pure-frontend** build, and the season recaps + a future manager-GOAT ranking reuse the same
endpoint. The only genuinely new analytics in the near-term viz suite is **lineup efficiency**
(build #7).

## The visualization vocabulary (a shared visual grammar)

Charts should read as a *family*, with consistent encodings so the league develops a visual
language:

- **Gold** = championship · **💩 / brown** = Sacko · **era bands** shade the timeline · league
  palette throughout · season-correct names always (`period_team_name`).

Chart types, each tailored — not a generic dashboard widget. (`have` = primitive already in
`web/src/charts/`; `new` = a new chart component.)

- **Rank-race / bump chart** (`have`: `RankFlow`) — season standings flow; *add* title-gold and
  Sacko markers on the lines + a one-shot animation.
- **Dominance heatmap** (`have`: `Heatmap`) — the 12×12 rivalry matrix → click to a pairwise
  dossier; *reuse* for a weekly-scoring-intensity grid.
- **Value scatter** (`have`: `ScatterQuadrant`) — ADP vs points, quadrant-labelled
  steals / reaches / studs / busts; *reuse* for efficiency vs scoring.
- **Diverging bars** (`new`) — Luck (xW − actual wins): green = under-rewarded, red = lucky.
  Zero-centered; `BarCompare` doesn't do this today.
- **Legacy-spine** (`new`) — a manager's career finish-position line with championship-gold and
  Sacko markers; one image = a career. Establishes the marker grammar.
- **Beeswarm / strip** (`new`) — weekly-score distributions; boom-bust spread.
- **Streamgraph / stacked area** (`new`) — cumulative points, title-share over time, dynasty
  runs.
- **Annotated line** (`new`/extend `LineTrend`) — a rivalry's margin over time with famous games
  pinned.
- **Stacked breakdown bar** (`have`: `StackedBreakdown`) — box-score scoring composition; elevate
  for famous-game replays.
- **Small multiples** (`new`) — the season-recap stat grid.

---

## The backlog (scored; Relive / Reckon / Reveal)

Score = resonance × reach ÷ effort, coarse H/M/L. ★ = first target.

| Job | Card | Reson. | Reach | Effort | Notes |
|---|---|---|---|---|---|
| Relive | ★ **Season Story pages** | H | H | M | Per-season recap; anatomy below. First surface; pulls the substrate into being. |
| Reckon | **All-time Manager GOAT ranking** | H | H | M | Defensible + explainable; reuses xW + efficiency + era-adj. Guaranteed argument. |
| Reckon | **Luck ledger / xW** (standalone view) | H | M | M | Keystone metric, also its own surface. |
| Reveal | **Auto-awards** (Mr. Consistency, Draft Heist, Bench Manager of Shame) | H | M | M | Pure conversation fuel; mostly existing analytics. |
| Reveal | **Season rank-race** chart | M | H | S | Half-built; drop into Standings + Season Story. |
| Relive | **Career legacy-spine** on each manager profile | M | M | S | Sparkline; high delight per unit effort. |
| Relive | **"On this day / anniversary"** Home hook | M | H | S | A reason to *return*. |
| Reckon | **Rivalry heatmap as centerpiece** | M | M | M | Elevate the matrix; click-through dossier. |
| Reveal | **Schedule-luck table** | M | M | S | Beloved FF argument; falls out of xW. |
| Relive | **Dynasty / era ribbon** | M | M | M | Title-holder timeline; the league's "ages." |
| Share | **Shareable cards / permalinks** | M | H | M | Record / championship / rivalry / legacy as one droppable image. |
| Data | **League lore ledger** (see below) | H | H | L | Unlocks the entire narrative layer. Ongoing. |

---

## First target — Season Story pages (on the metrics + viz substrate)

One page per season, blending **objective** (auto-composed) and **subjective** (curated). Why
this first: it is the smallest surface that *forces* the reusable substrate into existence — the
all-play/xW module, the rank-race + diverging-bar primitives, and lore-ledger v0 — while
delivering an immediately compelling thing on its own.

**Anatomy (per season):**
- **Hero** — champion (gold) + Sacko (💩) + a one-line season identity (curated).
- **The Defining Game** — highest-leverage / closest title-deciding matchup → deep-link to box
  score.
- **Biggest Upset** — largest xW-defying result.
- **Luckiest & Unluckiest** — xW − wins extremes.
- **Draft Heist & Bust of the year** — ADP value extremes.
- **The Trade / key move** — curated + FAAB.
- **Scoring leader** + a season scoring-distribution viz (era inflation visible).
- **Season rank-race** chart.
- **Subjective recap** — member-editable prose: *"what this season is remembered for."* This is
  lore-ledger v0.

**This build naturally spawns (in order):**
1. `analytics/` all-play / Expected-Wins module + tests (keystone; reused everywhere).
2. Bump-chart + diverging-bar chart primitives (reused everywhere).
3. The Season Story page composing existing draft/FAAB/scoring analytics.
4. A minimal curated per-season blurb field — **lore-ledger v0**.

Follow the project's PLAN → BUILD → VERIFY discipline: the next step is a `docs/plans/` plan for
build #1 (the all-play module), not implementation here.

---

## The data side — the league lore ledger (the deep gap)

The narrative layer is starved for the league's *qualitative* memory. Seed it incrementally,
member-supplied, structured enough to render but loose enough to capture real lore:

- **Season blurbs** — "what this season is remembered for" (starts in Season Story v0).
- **Rivalry origin stories** + nicknames + the season each turned personal.
- **Member bios / era labels** — who's who, when they joined/left, their reputation.
- **Memorable quotes, the *why* behind a Sacko, famous trades, make-believe drama.**

This is the highest-leverage *data* investment of the leg and likely touches `../danger-zone`
(or a dashboard-owned curation store, given read-only constraints — decide in its own plan).
Builds toward, and reuses, `curated_events.py` / `owner_story.py`.

---

## Out of scope (still NOT this leg)

- **Phase 3** — competitive edge / predictions / trade-lineup advice. The metrics here *reveal
  the past*; they must not tip into *advising the future*.
- Writing to league data; auth/hosting/multi-user; real-time scoring; native mobile. Same
  Phase 2 boundaries as always.
