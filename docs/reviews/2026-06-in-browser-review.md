# In-browser review — 2026-06

**Purpose:** systematic click-through of the dz-dashboard SPA against the real Phase 1 DB to
surface data gaps, honesty-affordance violations, and UX/presentation bugs.

> **Coverage note (post-F-51):** early findings in this review were recorded before the 2026-06-06
> DB regen reconstructed pre-2016 per-player scoring. Treat old "2010–2015 unscored" evidence as
> historical unless a later F-51/P2-redo note says it still applies. Current truth:
> `player_stats_scored` spans 2010–2025; the normal unscored gap is the current/in-progress season,
> data-driven on `is_scored`.

**Method — observe-only.** This session records findings; it does **not** fix code, run the
gate, or touch CI. Fixes are deferred to a small number of batched fix-passes downstream
(see "Proposed fix passes"), each its own PLAN→BUILD→VERIFY thread with a single gate + CI
run. This batching is deliberate: it prevents the piecemeal refactor/test/lint/CI churn that
makes on-the-spot fixing expensive.

**Triage shortcut (don't deep-read source):** to pin a finding's layer, hit the BFF directly
(`curl -s http://127.0.0.1:8800/v1/...`) and compare the JSON to the screen.
- Wrong/absent in the API response → `data` / `analytics` / `api-contract`.
- Correct in API but wrong on screen → `frontend-presentation`.
- Bare `0` / dash where data is absent → `gap-affordance` (must be `DataGap`).

---

## Coverage checklist

Tick each view as it's walked. Probe known gap zones: the current/in-progress unscored season
when `is_scored:false`, current-season-only availability, partial DST, and seasons without
captured drafts.

- [x] home
- [x] standings (+ timeline, week-stepper)
- [x] managers — index
- [x] managers — profile (trophy case, trajectory, season table, rivalry snapshot)
- [x] matchups — week grid (+ week-stepper)
- [x] matchups — box score (optimal lineup, left-on-bench, expandable breakdowns)
- [x] records
- [x] rivalries — matrix
- [x] rivalries — pairwise
- [x] players — index (search / filter)
- [x] players — detail (scoring chart, ownership timeline, availability)
- [x] stats
- [x] teams (roster-by-week, schedule, scoring trend, transactions)
- [x] draft
- [x] power
- [x] search
- [x] about / coverage

---

## Findings

<!--
Copy this template per finding. Keep entries terse; evidence is a curl snippet or a one-line
response excerpt, not a paragraph.

### F-NN — <short title>
- View/route:
- Observed:
- Expected:
- Severity: blocker | major | minor | polish
- Layer: data | analytics | api-contract | frontend-presentation | gap-affordance
- Evidence: <curl snippet / response excerpt / screenshot path>
- Suspected location: <one file:symbol, if known — unverified>
- Batch: see assignment map under "Proposed fix passes"
-->

### F-01 — Home curation: wrong components surfaced (data shown is accurate)
- View/route: `/` (home)
- Observed: Home currently surfaces — "scored era (10 years)" stat, a 2025-leader callout,
  and "power model top movers". All values render **accurately**; the complaint is *what* is
  chosen for the front door, not correctness.
- Expected: Re-curate home around season-relevant, seasonally-aware modules.
  - **Drop:** scored-era / "10 years" stat; 2025-leader callout (redundant — implied by the
    2025 champion); power-model top-movers (power-ranking system is suspected — poorly
    explained, possibly not durable; see related power-view finding).
  - **Add (always):** full-season standings; expanded records list (more record categories
    than today's home shows).
  - **Add (off-season, current date is off-season):** completed playoff bracket from last
    season; top-scoring players from the past year; recent-activity feed.
  - **Add (in-season):** this week's matchups; top-scoring players this week; recent-activity
    feed (transactions are tracked **in-season only** → feed is quiet/empty in off-season).
  - Implies a **season-phase signal** (in-season vs off-season) to switch the layout.
- Severity: major
- Layer: frontend-presentation (composition/curation); a recent-activity/transactions feed
  and last-season playoff bracket may need backend support — confirm endpoints exist in a
  later pass.
- Evidence: product judgment from walkthrough; `/v1/meta` confirms off-season context today
  (scored 2016–2025, `availability_current_season_only:true`). Data accuracy not in dispute.
- Suspected location: `web/src/features/home/` (HomePage composition); season-phase helper TBD.
- Batch: see assignment map under "Proposed fix passes"

### F-02 — Standings timeline tooltip + color polish
- View/route: standings → timeline chart (`/v1/seasons/{id}/standings/timeline`)
- Observed: Timeline renders and is a genuinely good insight, but the tooltip (a) shows a bare
  week number, (b) lists owners in a **fixed/stable order** regardless of the hovered week, and
  (c) the line palette **repeats colors** across the 12 teams.
- Expected: (a) label "Week N"; (b) order owners by **their rank in that week** (so the tooltip
  reads as that week's standing); (c) 12 visually distinct colors, one per team.
- Severity: minor (polish)
- Layer: frontend-presentation
- Evidence: visual walkthrough; timeline endpoint returns per-week ranks, so rank-ordering the
  tooltip is a presentation change only.
- Suspected location: `web/src/features/standings/` (timeline chart component + tooltip).
- Batch: see assignment map under "Proposed fix passes"

### F-03 — Standings: room for one more insight module
- View/route: standings page
- Observed: Page has the table + timeline; feels like it has headroom for one more "cool insight".
- Expected: Add a second analytical module (model to propose + implement — e.g. luck/expected-wins,
  points-for vs. finish, longest streaks). Open-ended; decide in the fix-pass plan.
- Severity: polish (enhancement)
- Layer: frontend-presentation (may need a small analytics helper depending on the chosen insight)
- Evidence: product judgment.
- Suspected location: `web/src/features/standings/`; possible `analytics/standings.py` helper.
- Batch: see assignment map under "Proposed fix passes"

### F-04 — Completed season should show playoff placements
- View/route: standings page (completed seasons)
- Observed: For a completed season, standings show regular-season rank but not the end-of-year
  **playoff finish** (champion, runner-up, 3rd, …) as a first-class element.
- Expected: Surface playoff placements/badges (champion, 2nd, etc.) when the season is complete.
- Severity: minor
- Layer: frontend-presentation — **data already present**: standings rows carry `final_rank`
  and `/v1/seasons` carries `champion`; this is rendering, not new analytics.
- Evidence: `curl /v1/seasons/2/standings` → every row has `final_rank`; `/v1/seasons` →
  `champion:{...}` per season.
- Suspected location: `web/src/features/standings/`.
- Batch: see assignment map under "Proposed fix passes"

### F-05 — Manager → roster not reachable from Managers panel
- View/route: `/managers` (index) → manager click-through
- Observed: From the Managers panel you can't reach a manager's roster. Expected to land on
  the **most recent season's ending roster** when clicking through.
- Expected: Clicking a manager surfaces (or links to) their latest-season ending roster.
- Severity: major
- Layer: frontend-presentation (linking) — **data exists** at `/v1/teams/{team_id}/roster`,
  but it's keyed by **team_id**, while owner profiles (`/v1/owners/{owner_id}`) expose only
  seasons/trajectory/head-to-head. Needs an owner→(latest-season team_id) hop then the team
  roster endpoint. Couples to F-06 (owner vs team identity).
- Evidence: OpenAPI — roster routes are all `/v1/teams/{team_id}/*`; no owner roster route.
- Suspected location: `web/src/features/managers/` (profile/index linking) + owner→team map.
- Batch: see assignment map under "Proposed fix passes"

### F-06 — Owner-vs-team identity model gap (DEFERRED — needs ownership-history research)
- View/route: `/managers` (index) — conceptual, affects multiple views
- Observed: League has always had **12 teams**, but **ownership has changed hands** over 16
  seasons. So league history has **>12 distinct owners**, while the same 12 team identities
  persist. Consequence: all 12 *teams* have 16 seasons (so "16 seasons" is **not** an
  insightful per-manager stat), but **owners** have varying tenures.
- Expected: A team-vs-owner identity model that distinguishes the persistent team line from
  its succession of owners, so per-manager stats reflect true owner tenure (not the team's).
  **Cannot be modeled now** — requires user research into the actual ownership-succession
  history. Flag as expected and prepare the schema/affordances for it.
- Severity: major (deferred / blocked on external research)
- Layer: data / analytics (identity model) — surfaces in managers, standings, records, rivalries.
- Evidence: product/domain knowledge from the league owner; `/v1/owners` vs `/v1/teams`
  currently treat owner and team as near-equivalent.
- Suspected location: identity mapping spanning `ff_pipeline` data + `analytics/owners.py`;
  needs an ownership-history source first.
- Batch: see assignment map under "Proposed fix passes"

### F-07 — Managers index sort is one-directional
- View/route: `/managers` (index)
- Observed: Column sorting only sorts one direction; can't toggle ascending/descending.
- Expected: Click toggles asc ↔ desc (standard table sort).
- Severity: minor
- Layer: frontend-presentation
- Evidence: visual walkthrough.
- Suspected location: `web/src/features/managers/` (index table sort handler).
- Batch: see assignment map under "Proposed fix passes"

### F-08 — Trophy case display is awkward
- View/route: manager profile → trophy case
- Observed: Trophy-case layout reads awkwardly.
- Expected: A cleaner presentation (model to try alternatives and pick).
- Severity: polish
- Layer: frontend-presentation
- Evidence: visual walkthrough.
- Suspected location: `web/src/features/managers/` (profile trophy-case component).
- Batch: see assignment map under "Proposed fix passes"

### F-09 — Manager profile: room for one more insight module
- View/route: manager profile
- Observed: Trajectory + rivalry snapshot are well-received "cool insights"; page has headroom
  for one more. (Pattern to learn from for new insight ideas: rank-trajectory over time,
  pairwise rivalry richness — analytical, comparative, time-aware.)
- Expected: Add one more analytical module (model to propose + implement).
- Severity: polish (enhancement)
- Layer: frontend-presentation (+ possible small analytics helper)
- Evidence: product judgment.
- Suspected location: `web/src/features/managers/`.
- Batch: see assignment map under "Proposed fix passes"

### F-10 — Season table doesn't show a result/finish for all seasons
- View/route: manager profile → season table
- Observed: Table is accurate (incl. 2010–2015) but does not show a **result/finish** for every
  season; it should be present for all completed seasons.
- Expected: A per-season result (playoff finish / champion / made-playoffs) on every completed row.
- Severity: minor
- Layer: data / analytics — `/v1/owners/{id}/seasons` returns `made_playoffs: null` for **all**
  rows, while `final_rank` + `is_champion` are populated. So if "result" = playoff outcome, the
  `made_playoffs` signal is uncomputed (data/analytics); if final-rank-derived, it's a frontend
  render. Fix-pass to pick the source.
- Evidence: `curl /v1/owners/5/seasons` → every row `made_playoffs:null`, `final_rank` present.
  Also: `team_id` differs each season for one owner (17→29→41→53→65→77→89…) — corroborates F-06.
- Suspected location: `analytics/owners.py` (season list / `made_playoffs`) and/or
  `web/src/features/managers/` season table.
- Batch: see assignment map under "Proposed fix passes"

### F-11 — Rivalry snapshot "24g" label is unclear
- View/route: manager profile → rivalry snapshot
- Observed: Games-played renders as e.g. "24g", which reads as "24 grams" not "24 games".
- Expected: Clearer label (e.g. "24 GP", "24 games") and better styling.
- Severity: minor (polish)
- Layer: frontend-presentation
- Evidence: visual walkthrough.
- Suspected location: `web/src/features/managers/` (rivalry-snapshot component).
- Batch: see assignment map under "Proposed fix passes"

### F-12 — Enrich rivalry snapshot (cumulative +/-, closest game, biggest blowout w/ links)
- View/route: manager profile → rivalry snapshot
- Observed: Snapshot under-surfaces data the head-to-head endpoint already provides, and is
  missing two desired metrics.
- Expected: Show — total cumulative +/- points vs that owner across all meetings; **closest
  game** and **biggest blowout** scores, each linking to that matchup's box-score page.
- Severity: minor (enhancement)
- Layer: split —
  - **biggest blowout + link: already in API** → `most_lopsided_meeting{margin_for_a,matchup_id}`;
    pure frontend (surface + deep-link to `/seasons/{id}/weeks/{wk}/matchups`).
  - **closest game (smallest margin): NOT in API** → analytics addition to head-to-head.
  - **cumulative +/- points: NOT in API** (only `avg_margin_for_a`) → analytics addition.
- Evidence: `curl /v1/owners/5/head-to-head/1` → has `avg_margin_for_a`,
  `highest_scoring_meeting{matchup_id}`, `most_lopsided_meeting{matchup_id}`; no closest-game,
  no cumulative total.
- Suspected location: `analytics/head_to_head.py` (+ schema) and
  `web/src/features/managers/` rivalry snapshot.
- Batch: see assignment map under "Proposed fix passes"

### F-13 — Add a close-game flag (mirror the blowout flag)
- View/route: matchups → week grid
- Observed: Blowout flag is a liked insight; there's no symmetric **close-game** flag.
- Expected: A close-game flag for small-margin matchups.
- Severity: minor (enhancement)
- Layer: analytics (threshold) + frontend — `margin` is already in the matchups payload;
  prefer the close/blowout threshold live backend (no metric math in web), mirroring blowout.
- Evidence: `curl /v1/seasons/4/weeks/6/matchups` → each game has `margin`.
- Suspected location: `analytics/matchups.py` (flag) + `web/src/features/matchups/` grid.
- Batch: see assignment map under "Proposed fix passes"

### F-14 — Color the matchup margin +/- per side (green/red)
- View/route: matchups → week grid
- Observed: Margin isn't color-coded per side.
- Expected: Render each side's +/- margin in green (winner) / red (loser).
- Severity: polish
- Layer: frontend-presentation (`margin`/`is_winner` already in payload).
- Evidence: matchups payload has `margin`, `is_winner`, `winner_team_id`.
- Suspected location: `web/src/features/matchups/` grid card.
- Batch: see assignment map under "Proposed fix passes"

### F-15 — Week stepper should allow direct week selection
- View/route: matchups → week-stepper (also applies to standings week-stepper)
- Observed: Stepper only steps ±1; no way to jump directly to a week.
- Expected: Dropdown or a clickable list of all week numbers (1–17; 16 in older seasons).
- Severity: minor
- Layer: frontend-presentation
- Evidence: visual walkthrough.
- Suspected location: shared week-stepper component under `web/src/`.
- Batch: see assignment map under "Proposed fix passes"

### F-16 — Unscored-era "incomplete" flag over-claims at the matchup grid
- View/route: matchups → week grid, 2010–2015 (probed 2012 wk6)
- Observed: 2012 wk6 team scores + margins are **full and accurate**, yet the era still carries
  an "incomplete/unscored" affordance (season `is_scored:false`). The honesty layer is firing a
  false negative — labeling correct, complete grid data as incomplete. User believes the flag is
  stale (not 100% confirmed; depends on player-level box-score completeness — see box-score view).
- Expected: Grid-level results for 2010–2015 should **not** be flagged incomplete; the gap
  affordance must be scoped to the layer that's actually missing (player-level fantasy scoring),
  not the whole season. Reword: regular-season results + team totals **are** available
  2010–2015; only per-player fantasy points are absent. Decouple the affordance from blanket
  season-level `is_scored`.
- Severity: major (honesty-layer correctness — mislabels good data, erodes trust)
- Layer: gap-affordance + api-contract (`box-score` returns `reason:"season_unscored"`).
  **RESOLVED scope (DB probe):** per-player **scored** points genuinely absent 2010–2015
  (`player_stats_scored` has rows only for 2016–2025), so the box-score "Not scored" gap is
  **honest**. But team totals are real, so the grid/season-level wording over-claims. Fix is
  precision of the affordance, not surfacing hidden data.
- Evidence: `curl /v1/seasons/4/weeks/6/matchups` → `is_scored:false` yet real
  `team_a.score`/`team_b.score`/`margin`. `curl /v1/matchups/957/box-score` →
  `available:false, reason:"season_unscored", home:null`. DB (ro): `player_stats_scored`
  seasons = {2016…2025}; `player_stats_raw` seasons = {2010…2025}.
- Suspected location: season `is_scored`→affordance mapping in `web/src/features/matchups/`;
  box-score gap copy; `is_scored` wording in meta/analytics.
- Batch: see assignment map under "Proposed fix passes"

### F-17 — Show entering W/L record at matchup start
- View/route: matchups → week grid (matchup panels)
- Observed: Panels show only the game result, not each owner's W/L **entering** the game.
- Expected: Show entering record per side (e.g. 1-0 / 0-1 / 0-0-1 for a Week 2 matchup).
- Severity: minor (enhancement)
- Layer: data / analytics — **not in API**; needs an entering-record computation per matchup.
- Evidence: matchups payload carries no per-team record field.
- Suspected location: `analytics/matchups.py` (+ schema) and `web/src/features/matchups/`.
- Batch: see assignment map under "Proposed fix passes"

### F-18 — Box-score expandable breakdown could be more insightful (2025)
- View/route: matchups → box score (scored era) → per-player expandable breakdown
- Observed: 2025 box score is accurate; the expandable per-player breakdown is a liked insight
  but feels like it could go deeper / be cooler.
- Expected: Richer per-player breakdown (model to propose — e.g. stat-line → points derivation,
  vs-position rank that week, share of team total, start/sit value).
- Severity: polish (enhancement)
- Layer: frontend-presentation (+ possible analytics if new per-player metrics are added)
- Evidence: visual walkthrough; `player_stats_scored` + `player_stats_raw` both present for
  2016–2025, so stat-line context is available to enrich the breakdown.
- Suspected location: `web/src/features/matchups/` box-score; `analytics/box_score.py` if enriched.
- Batch: see assignment map under "Proposed fix passes"

### F-19 — Record deep-links land on generic, sometimes unhelpful pages
- View/route: `/records` → per-record links
- Observed: Score/matchup records (highest/lowest team score, blowout, narrowest, highest-scoring
  matchup) link **correctly** to the matchup. But:
  - **best player week / best season** link to the generic player/owner page, not a
    record-specific destination.
  - **longest win / loss streak** link to the manager page, where the streak isn't viewable →
    unhelpful.
  - **closest rivalry** links to the pairwise rivalry page (an appropriate endpoint) but that
    page doesn't actually explain/justify the "closest" claim (couples to F-12).
- Expected: Each record links to a destination that *shows the record* — e.g. best-player-week →
  that week's box score with the player highlighted; streaks → the matchup span; closest-rivalry →
  an enriched pairwise page that surfaces the closeness metric.
- Severity: minor
- Layer: frontend-presentation (link targets); some destinations/anchors may not exist yet.
- Evidence: walkthrough; `/v1/records` categories listed.
- Suspected location: `web/src/features/records/`.
- Batch: see assignment map under "Proposed fix passes"

### F-20 — Expand the records catalog (new "cool insight" records)
- View/route: `/records`
- Observed: Current categories are score/season/streak/championship oriented; many high-interest
  records are missing.
- Expected: Add records such as — player on the most owners' rosters across years; most
  added/dropped player; highest avg transactions per owner per year; most trades; best draft
  performance; (more, model to brainstorm). These are roster/transaction/draft aggregations.
- Severity: minor (enhancement; sizeable scope)
- Layer: data / analytics (new aggregations) + api-contract + frontend.
- Evidence: product judgment; `/v1/records`, `/v1/records/draft`, `/v1/records/championships`
  exist as the extension surface.
- Suspected location: `analytics/records.py` (+ schema, route) and `web/src/features/records/`.
- Batch: see assignment map under "Proposed fix passes"

### F-21 — Add a league-wide trophy case to the Records section
- View/route: `/records`
- Observed: No aggregate trophy case in this section.
- Expected: A league-wide trophy case with search/filter access (distinct from the per-manager
  trophy case in F-08).
- Severity: minor
- Layer: frontend-presentation — championship data exists at `/v1/records/championships`.
- Evidence: `/v1/records/championships` route present.
- Suspected location: `web/src/features/records/`.
- Batch: see assignment map under "Proposed fix passes"

### F-22 — Team-level records wrongly scoped to the scored era (exclude 2010–2015)
- View/route: `/records`
- Observed: Records payload carries a `scored_era` scope and **all team-level records cite 2016+**
  (highest_team_score 2019, lowest 2022, highest_scoring_matchup 2019, best/worst season PF
  2019/2018). But team totals are **valid and present for 2010–2015** — so these records are
  computed over the wrong window. A pre-2016 game/season could be the true record.
- Expected: Team/score/season-level records range over **all seasons with team totals**
  (2010–2025). Only player-dependent records (best_player_week) stay scoped to 2016–2025.
- Severity: major (record **values may be incorrect**, not merely incomplete)
- Layer: analytics (records scoping) — separate the scored-era gate (player records) from the
  full-history gate (team/score records).
- Evidence: `/v1/records` → `scored_era` list present; every team record `season_year` ≥ 2019;
  team totals exist 2010–2015 (`/v1/seasons/4/weeks/6/matchups` had real scores). Fix-pass must
  recompute against pre-2016 team data and verify whether any pre-2016 game/season takes a record.
- Suspected location: `analytics/records.py` (era scoping per category).
- Batch: see assignment map under "Proposed fix passes"

### F-23 — Pairwise rivalry page is thin and some labels are vague
- View/route: `/rivalries` → pairwise (also the target of records' "closest rivalry" link, F-19)
- Observed: Matrix is solid. Pairwise shows all expected head-to-head values but feels thin for
  how much history exists between two owners; some labels are vague, e.g. "avg margin (for
  <owner>) X pts/game" doesn't read clearly.
- Expected: Clarify labels (e.g. "<owner> averages +14.9 pts/game in this matchup") and expand
  what's surfaced — per-season breakdown, closest game + biggest blowout (linked), cumulative
  +/- points, playoff meetings, current rivalry streak. Re-think for insight + clarity.
- Severity: minor (enhancement)
- Layer: frontend-presentation (clarity/expansion) + analytics (closest game, cumulative +/-).
  **Couples with F-12** — same `head-to-head` endpoint; enrich the analytics **once** and
  surface in both the manager-profile snapshot (F-12) and this pairwise page.
- Evidence: `/v1/owners/5/head-to-head/1` has `avg_margin_for_a`, `highest_scoring_meeting`,
  `most_lopsided_meeting` (linkable) but no closest-game / cumulative-+/- / per-season split.
- Suspected location: `analytics/head_to_head.py` (+ schema) and `web/src/features/rivalries/`.
- Batch: see assignment map under "Proposed fix passes"

### F-24 — Drop the `scope=all` option and the `has_scored` flag from the players UI
- View/route: `/players` index (+ contract)
- Observed: The index exposes a `scope` toggle (`league`/`all`) and a `has_scored` marker per row.
- Expected (user directive): This app is **danger-zone-league-specific**. Players never rostered
  during league tenure (2010–2026+) should **not be visible anywhere in the app** → remove the
  `scope=all` affordance entirely; league-relevance is the only mode, enforced app-wide. Also
  **drop `has_scored`** from the UI — it's uninformative (all indexed players are assumed
  league-relevant). Keep the **rostered-season span** (review accuracy in the major pass, F-25).
- Severity: major
- Layer: frontend-presentation + api-contract (remove `scope` param / `has_scored` field).
- Evidence: `/v1/players` params include `scope`; rows include `has_scored`.
- Suspected location: `api/routes/players.py` (`scope`), `analytics/players.py:list_player_index`,
  schema `PlayerIndexRow`, `web/src/features/players/PlayersPage.tsx`.
- Batch: see assignment map under "Proposed fix passes"

### F-25 — Roster→player match leakage: ghost/mismatched index entries (MAJOR data pass)
- View/route: `/players` index (and any player surface)
- Observed: `A.B. Brown` (player_id 3689) is the first index entry, `scope:league`,
  `first_rostered_season:2012, last_rostered_season:2013` — but the real A.B. Brown last played
  in the NFL in **1992**, never during league tenure. This is a **roster→player ID mismatch**:
  `team_rosters` matched a real 2012–2013 roster slot to the wrong nflverse player (the documented
  abbreviated-name / stub-duplicate failure mode). The league-scope filter can't catch it because
  `team_rosters` vouches for the bad match. Likely many similar undiscovered mismatches/omissions.
- Expected: A thorough, **automated, self-informing** cleanup pass that reconciles `team_rosters`
  → player identity against the league's actual rostered history, removing ghosts and fixing
  mis-matches — **driven by the app's stated purpose** (danger-zone-specific, complete, no
  superfluous out-of-scope players), **not** granular per-case decisions by the user. Also
  re-verify rostered-span accuracy here.
- Severity: blocker (data integrity — corrupts the index, bios, and any roster-derived view)
- Layer: data (Phase-1 `team_rosters`→player matching) — surfaces through `analytics/players.py`.
- Evidence: `/v1/players?name=Brown&scope=league` → A.B. Brown rostered 2012–2013, has_scored=false;
  external fact: real A.B. Brown's last NFL season was 1992. His detail/search shows roster weeks
  **2012 wk3–16 and 2013 wk0–16** — note the suspicious **week 0** entry (likely a preseason/import
  artifact worth auditing in the same pass).
- Suspected location: Phase-1 roster→player matching (`ff_pipeline`); precedent for triage→ship:
  `docs/archive/players-audit-dashboard.md` + `docs/handoffs/players-audit-danger-zone.md`.
- Note: per CLAUDE.md, Phase-1 changes are restricted to additive read-only helpers; if the fix
  must mutate `team_rosters` matching it belongs in the **pipeline repo**, not the dashboard —
  scope that boundary explicitly in the pass's PLAN session.
- Batch: see assignment map under "Proposed fix passes"

### F-26 — Pre-2016-only rostered players present as statless (looks like an error)
- View/route: `/players` index + detail
- Observed: `Aaron Hernandez` is legitimately rostered **2010–2012** (`has_scored:false`); his entire
  tenure is in the unscored era, so he has no reconstructed fantasy points and appears statless —
  indistinguishable from a ghost/error to the user.
- Expected: Affordance that explains "rostered in the unscored era (2010–2015) — no fantasy scoring
  reconstructed", and/or surface his **raw** stat lines (which exist, see Key data fact). Never let
  a real league player read as empty/erroneous.
- Severity: minor (honesty/affordance)
- Layer: gap-affordance + frontend; raw stats exist (`player_stats_raw` covers 2010–2025).
- Evidence: `/v1/players?name=Hernandez` → rostered 2010–2012, has_scored=false.
- Suspected location: `web/src/features/players/` detail empty-state; couples to F-16 / Key data fact.
- Batch: see assignment map under "Proposed fix passes"

### F-27 — Pre-2016 weekly fantasy scoring absent everywhere (cross-cutting DECISION)
- View/route: player detail scoring chart; also box scores (F-16), player-week records (F-22),
  Hernandez (F-26).
- Observed: Weekly fantasy scoring is empty for every pre-2016 season — scoring charts, box
  scores, and player-week records all blank for 2010–2015. User has repeatedly stated this "should
  be available already."
- Expected: **Reconstruct 2010–2015 fantasy scoring** — the user confirms this is the desired end
  state and it is **feasible**. Inputs all exist: nfl.com scraped league scores (definitive truth,
  the source of the existing team totals) **and** player stat lines (`player_stats_raw`, definitive).
  The reason scoring was never applied: league scoring **rules changed at several points** in
  2010–2015. Method:
  1. For each pre-2016 season, **discover that season's scoring settings** by reconciling
     `player_stats_raw` against the definitive nfl.com scores — where applying current rules drifts
     from the nfl.com truth reveals the era's rule deltas.
  2. **Confirm + log** each season's settings (a per-season scoring-rules ledger).
  3. Apply the discovered settings to produce `player_stats_scored` for 2010–2015; thereafter
     stats:scoring can be **self-validated** (raw → settings → score == nfl.com truth) without
     relying solely on the scraped scores.
  Outcome: resolves most coverage gaps and makes the coverage/About page largely obsolete. Several
  findings collapse when this lands: F-16, F-22 (player records), F-26, F-39 (draft value pre-2016).
- Severity: major (cross-cutting; this is the dashboard's strategic north star — "all league years,
  accurate scoring/players/owners")
- Layer: data — **Phase-1 / pipeline scoring reconstruction**; escalate as its own program, not a
  dashboard fix. Backed by the per-season league-settings ledger (see cross-cutting theme below).
- Evidence: DB (ro) `player_stats_scored` seasons {2016…2025}; `player_stats_raw` {2010…2025};
  team totals already present for 2010–2015 (from nfl.com scrape). Hernandez detail: bio+ownership
  render, scoring chart empty. User confirms inputs are present and reconstruction is the goal.
- Suspected location: pipeline scoring (`ff_pipeline`) + a per-season scoring-rules ledger.
- Batch: see assignment map under "Proposed fix passes"

### F-28 — Ownership timeline still too verbose
- View/route: player detail → ownership timeline
- Observed: Timeline is complete and accurate (Phase-A span collapse held) but still reads verbose.
- Expected: Collapse further into shorter, scannable info blocks.
- Severity: minor (polish)
- Layer: frontend-presentation (possibly tune span granularity in `ownership_timeline`).
- Evidence: walkthrough; `analytics/players.py:ownership_timeline` already produces spans.
- Suspected location: `web/src/features/players/PlayerDetailPage.tsx` (ownership block).
- Batch: see assignment map under "Proposed fix passes"

### F-29 — Availability section: deprioritize off-season, replace with a player insight module
- View/route: player detail → availability
- Observed: Availability is empty/irrelevant in the off-season (current-season-only data).
- Expected: Deprioritize availability until in-season; for now replace it with a player-focused
  "insight" module (give it a better name than "cool insights"). Implies the same season-phase
  awareness as F-01.
- Severity: minor (enhancement; seasonal)
- Layer: frontend-presentation (+ season-phase signal shared with F-01).
- Evidence: `/v1/meta` `availability_current_season_only:true`; off-season today.
- Suspected location: `web/src/features/players/PlayerDetailPage.tsx`; season-phase helper (F-01).
- Batch: see assignment map under "Proposed fix passes"

### F-30 — Stats explorer default should be season totals
- View/route: `/stats`
- Observed: Explorer supports season totals, weekly leaders, position/season/team filters, but the
  default landing isn't season totals.
- Expected: **Season totals** as the default view; top weekly scoring totals reachable as a
  navigable area from there.
- Severity: minor (IA / default)
- Layer: frontend-presentation.
- Evidence: walkthrough; `/v1/stats/season-totals` exists.
- Suspected location: `web/src/features/stats/`.
- Batch: see assignment map under "Proposed fix passes"

### F-31 — Season totals include NFL playoff games (should be fantasy weeks only)
- View/route: `/stats` → full season player stats (season totals)
- Observed: Season totals include **NFL playoff games**, inflating totals with games outside the
  fantasy season.
- Expected: Totals scoped to the **fantasy season only (weeks 1–17)**; exclude NFL post-season /
  weeks beyond the fantasy schedule.
- Severity: major (totals are inflated / inaccurate)
- Layer: analytics (season-totals week filter).
- Evidence: user observation (authoritative on league); fix-pass to confirm week range in
  `season-totals` aggregation.
- Suspected location: `analytics/stats.py` (or wherever season-totals aggregates) — week cap.
- Batch: see assignment map under "Proposed fix passes"

### F-32 — Fantasy-phase week filters + historically-accurate season-length model (app-wide)
- View/route: `/stats` (filters); model affects standings/records/matchups app-wide
- Observed: No way to filter by fantasy phase; and the fantasy schedule **changed length over
  time** (regular season 1–13 → 1–14; playoffs 14–16 → 15–17; championship wk16 → wk17).
- Expected: Add phase filters — fantasy regular season (1–14, prev 1–13), playoffs (15/16/17,
  prev 14/15/16), championship (wk17, prev wk16). Back it with a **per-season week-structure
  model** enforced historically. **Switch year is TBD** — user will supply later; **expect and
  prepare for it**. NB: standings already reports `regular_season_weeks:14` for 2010, which may
  be historically wrong under the "prev 1–13" rule — same model must fix that.
- Severity: major (mis-classifies regular vs playoff weeks across the app)
- Layer: data / analytics (season-schedule model) + frontend filters.
- Evidence: user (authoritative); `/v1/seasons/2/standings` → `regular_season_weeks:14` for 2010.
- Suspected location: a season-schedule config/helper consumed by `analytics/` (standings,
  records, stats); `web/src/features/stats/` filters.
- Batch: see assignment map under "Proposed fix passes"

### F-33 — Pre-2016 gap affordance is stark across views (copy unification)
- View/route: `/stats` pre-2016 ("No scores / No scored data for this scope."); also box scores,
  player charts.
- Observed: The pre-2016 empty-state is honest but stark/terse and worded inconsistently across
  views.
- Expected: One warm, consistent affordance explaining the unscored era (2010–2015: results &
  team totals exist; per-player fantasy scoring not reconstructed). Apply uniformly.
- Severity: polish (gap-affordance)
- Layer: gap-affordance / frontend-presentation.
- Evidence: stats pre-2016 message; couples to F-16, F-26, F-27.
- Suspected location: shared `DataGap` copy + per-view usages.
- Batch: see assignment map under "Proposed fix passes"

### F-34 — Team page season-year selector doesn't update the page
- View/route: team page → top-right season selector
- Observed: Selecting a new year doesn't change the team page; the shown season doesn't match the
  selected year.
- Severity: major (broken control)
- Layer: frontend-presentation (selector not wired to page state / refetch).
- Evidence: walkthrough.
- Suspected location: `web/src/features/teams/` (season selector → page state).
- Batch: see assignment map under "Proposed fix passes"

### F-35 — Team roster-by-week shows unscored flag pre-2016 despite complete data
- View/route: team page → roster-by-week, pre-2016
- Observed: Weekly roster renders accurately for pre-2016, yet an "unscored data" flag still shows.
- Expected: No incompleteness flag where the roster data is complete (extends F-16 — affordance
  must be scoped to the missing layer, not the whole season).
- Severity: minor (honesty over-claim)
- Layer: gap-affordance (season `is_scored`→flag); see F-16.
- Evidence: walkthrough.
- Suspected location: `web/src/features/teams/` roster section.
- Batch: see assignment map under "Proposed fix passes"

### F-36 — Schedule's matchup deep-link is broken pre-2016
- View/route: team page → schedule → matchup link (pre-2016)
- Observed: Schedule is accurate pre & post 2016, but the linked matchup page is **broken** for
  pre-2016 games.
- Expected: Pre-2016 matchup link should land on a valid page — render the team-total result view
  (which exists) instead of erroring on the absent player-level box score (couples to F-16).
- Severity: major (broken navigation)
- Layer: frontend-presentation (link target / pre-2016 matchup page handling).
- Evidence: walkthrough; `/v1/matchups/{id}/box-score` returns `available:false` pre-2016, so the
  box-score page likely errors instead of degrading to team totals.
- Suspected location: `web/src/features/matchups/` box-score route + `web/src/features/teams/` schedule link.
- Batch: see assignment map under "Proposed fix passes"

### F-37 — Transactions only shows drafted players; need full transaction history

**RESOLVED tier 1:** dashboard roster-diff derivation shipped in **PR #35**. Tier 2 (exact
transaction dates, waiver/FA/trade classification, FAAB bids) remains UP / Phase 1.

- View/route: team page → transactions
- Observed: "Transactions" shows only players **drafted** by the team — not adds/drops/trades/
  waivers across the season.
- Expected: Full transaction history. Separate **draft** transactions into their own space; show
  **in-season** free-agent/waiver/trade activity alongside. Surface FAAB bid info where applicable
  (the league switched from standard waiver order → FAAB at a historical point — **TBD, expect it**;
  same historical-model theme as F-32). Transactions are a rich source for records (F-20) and insights.
- Severity: major (core data feature largely absent)
- Layer: data + analytics + frontend.
- **Recommended resolution (asked of model):** two-tier —
  1. **Now, dashboard-scoped:** derive add/drop/retain by diffing **`team_rosters` week-over-week**
     (player appears = added, disappears = dropped, present N weeks = retained). Read-only, no scrape,
     ships in the dashboard; gives transaction *shape* without exact dates/bids. Game-time
     game-center rosters (e.g. 2012 wk10 post-MNF finals) are the authoritative weekly snapshot to diff.
  2. **Later, pipeline-scoped:** a new **nfl.com scrape pass** to capture the real transaction log
     (exact dates, waiver vs FA vs trade, FAAB bids). This is a **Phase-1** job — escalate as its
     own decision, not a dashboard fix.
- Evidence: `/v1/teams/{id}/transactions` route exists but is draft-only per walkthrough;
  `team_rosters` is week-grained and already read-only-available.
- Suspected location: `analytics/transactions.py` (roster-diff derivation) + schema/route +
  `web/src/features/teams/`; nfl.com scrape lives in `ff_pipeline`.
- Batch: see assignment map under "Proposed fix passes"

### F-38 — Draft value: expand into a robust, drillable insight space
- View/route: `/draft` → draft value
- Observed: Draft value is the **exemplar "cool insight"** — it captures the whole reason for this
  dashboard (personalized league insight nfl.com doesn't offer). Currently it's a single view.
- Expected: Click-through into steals/busts detail; sort by **position** and **round**; room to
  grow into a robust content area. Treat as the template for what a high-value insight should do.
- Severity: minor (enhancement; high product value)
- Layer: frontend-presentation + analytics (sortable/drillable draft-value).
- Evidence: `/v1/seasons/{id}/draft/value` exists.
- Suspected location: `analytics/draft.py` + `web/src/features/draft/`.
- Batch: see assignment map under "Proposed fix passes"

### F-39 — Draft value unavailable pre-2016 (depends on F-27 decision)
- View/route: `/draft` pre-2016 → cards read "Players not scored - value unavailable"
- Observed: Pre-2016 drafts are accurate (teams/order/picks) but have no draft-value insight
  because player scoring is absent.
- Expected: Rectify alongside the pre-2016 scoring decision (F-27) — if scored points are
  reconstructed upstream, draft value backfills automatically.
- Severity: minor (dependent on F-27)
- Layer: data (pre-2016 scoring, see F-27) → analytics draft-value.
- Evidence: walkthrough; couples to F-27 / Key data fact.
- Suspected location: `analytics/draft.py` value calc (needs scored points).
- Batch: see assignment map under "Proposed fix passes"

### F-40 — Draft board must render as a 12-column snake grid
- View/route: `/draft` → draft board
- Observed: Board isn't laid out in the standard fantasy draft-board format.
- Expected: Always 12 columns (one per drafting team), **snake order** by round — R1 picks 1–12
  L→R, R2 picks 13–24 R→L, R3 25–36 L→R, etc. (Consistent with the always-12-teams fact, F-06.)
- Severity: minor (presentation correctness for the signature draft view)
- Layer: frontend-presentation.
- Evidence: walkthrough; standard fantasy draft-board convention.
- Suspected location: `web/src/features/draft/` board component.
- Batch: see assignment map under "Proposed fix passes"

### Non-finding — no season is missing draft data
- Stepping 2010–2025: every season has accurate draft info (teams + order). The roadmap's
  "seasons without captured drafts" gap does not manifest in the real DB. No action.

### F-41 — Power ranking: keep, but revise methodology + verify inputs
- View/route: `/power`
- Observed: Ranking is sensible and *does* explain its method, but the method feels arbitrarily
  composed (auto-delivered, not user-informed). Earns its place as an insight but isn't highly
  compelling.
- Expected: Revise/expand the model toward something more compelling and league-informed; keep the
  on-page explanation. Also **verify the model's inputs**: confirm whether it depends on
  player-level scoring (which would compromise pre-2016, where it currently *looks* valid but is
  hard to verify) — if it's W/L + team points only, pre-2016 is sound.
- Severity: minor (enhancement)
- Layer: analytics (power model) + on-page methodology copy.
- Evidence: walkthrough; pre-2016 power renders and looks plausible but is unverified.
- Suspected location: `analytics/power.py` (+ methodology text in `web/src/features/power/`).
- Note: F-01 still stands — drop power **top-movers from the home view**; this keeps the
  **dedicated power view**, just improved.
- Batch: see assignment map under "Proposed fix passes"

### F-42 — Power timeline chart is noisy/confusing (shared with standings timeline)
- View/route: `/power` → power-over-time chart
- Observed: Rank-over-time chart is noisy and hard to read.
- Expected: Improve legibility (fewer crossing lines / better color separation / clearer hover) —
  same legibility problem as the standings timeline (F-02); both likely the **shared chart wrapper**
  (roadmap P9).
- Severity: minor
- Layer: frontend-presentation (shared chart component).
- Evidence: walkthrough; couples to F-02.
- Suspected location: shared chart wrapper under `web/src/`; `web/src/features/power/`.
- Batch: see assignment map under "Proposed fix passes"

### F-43 — Build an automated data-gap / correctness validation harness (process)
- View/route: cross-cutting (raised at `/power`, applies app-wide)
- Observed: Manually verifying whether gaps/values are correct (esp. pre-2016) is inefficient and
  memory-dependent; the user explicitly wants an automated way to double-check gaps.
- Expected: An automated audit harness that cross-checks the app's gap affordances and computed
  values against the DB — e.g. asserts "team totals present 2010–2015", "player scoring absent
  2010–2015", "no never-rostered players in the index", "records range over the correct window".
  This would have caught F-16, F-22, F-25, F-31, F-35 mechanically.
- Severity: minor (process/tooling; high leverage)
- Layer: testing / tooling (backend; read-only DB assertions).
- Evidence: user request; mirrors the players-audit automated approach (F-25).
- Suspected location: `tests/dashboard/` (a data-integrity/coverage test module) or a small audit script.
- Batch: see assignment map under "Proposed fix passes"

### F-44 — Global search bypasses the league-scope filter (ghosts resurface)
- View/route: global search
- Observed: Search returns never-rostered players that the players index correctly excludes. A.J.
  Feeley is **absent** from `scope=league` (`/v1/players?name=Feeley&scope=league` → `[]`) but
  global search surfaces him. So search queries the full nflverse universe, not the league-relevant
  set. (Distinct from F-25: Feeley has no `team_rosters` row at all — this is a scope-leak, not a
  bad match.)
- Expected: Search applies the same league-relevance scope as the index — never-rostered players
  appear nowhere (consistent with F-24's "no out-of-scope players anywhere").
- Severity: major (re-introduces the exact ghosts the players audit removed)
- Layer: data / api-contract (search query scope).
- Evidence: `scope=league` Feeley → `[]`; `scope=all` Feeley → present, rostered seasons NULL;
  search returns him anyway.
- Suspected location: the search endpoint/query (player branch) — apply the `team_rosters`-scoped
  filter used by `list_player_index`.
- Batch: see assignment map under "Proposed fix passes"

### F-45 — Team search is weak (NFL synonyms, players-by-team, fantasy team names)
- View/route: global search → teams
- Observed: Player + owner search is excellent (incl. "mike" → manager first, then players). Team
  search falls short:
  - NFL team nomenclature inconsistent: "New York" → only Giants (not Jets); "Jets" → "Jets" not
    "New York Jets".
  - Searching an NFL team doesn't surface its current players ("MIN"/"Minnesota"/"Vikings" → no
    Vikings players).
  - Fantasy team names aren't matched: "north" misses "...King in the Northvale" / "The Northvale
    Scumbags".
- Expected: NFL team matching across city + nickname + abbreviation (synonyms); searching a team
  surfaces its players; fantasy team names are searchable.
- Severity: major (search incomplete for a whole entity class)
- Layer: data / analytics (search matching: team synonyms, player→team, fantasy-team-name index).
- Evidence: walkthrough examples above.
- Suspected location: the search endpoint/query (team + fantasy-team branches).
- Batch: see assignment map under "Proposed fix passes"

### F-46 — Search dropdown can't scroll with many results
- View/route: global search → top-menu dropdown
- Observed: When there are many results, the dropdown can't be scrolled.
- Severity: minor
- Layer: frontend-presentation.
- Evidence: walkthrough.
- Suspected location: `web/src/` search dropdown component.
- Batch: see assignment map under "Proposed fix passes"

### F-47 — Add an automated search test suite (functional + security edge cases)
- View/route: global search (process)
- Observed: Search is only spot-checked manually; no systematic coverage.
- Expected: Automated tests — expected successes, expected failures, and **security edge cases**:
  script injection (XSS), prompt injection, uncleaned regex / special-char input. Verifies the
  search query is sanitized and the input is treated as data, not code/regex.
- Severity: minor (test/security hardening)
- Layer: testing / security (backend search + frontend input handling).
- Evidence: user request; pairs with F-43 automation theme.
- Suspected location: `tests/dashboard/` (search) + `web/` input sanitation.
- Batch: see assignment map under "Proposed fix passes"

### F-48 — Coverage page: DST gap undocumented; keep as dev-facing fact
- View/route: `/about` (coverage)
- Observed: Coverage page reads honestly but does **not** mention the DST gap. User: not required
  for end-users, but worth keeping for development / early-phase fact-checking.
- Expected: Record the DST status as a dev-facing note. Reconcile the conflict: `/v1/meta` claims
  `dst_scoring_complete:true`, but there's a known partial-DST concern (DST yards/sacks read low,
  rooted in nflverse team-defense upstream). Confirm which is authoritative; don't surface to
  end-users unless real.
- Severity: polish (dev documentation / data accuracy of a flag)
- Layer: data (meta flag accuracy) + docs.
- Evidence: `/v1/meta` `dst_scoring_complete:true`; known upstream DST yards/sacks gap.
- Suspected location: meta/coverage computation; dev docs.
- Batch: see assignment map under "Proposed fix passes"

### Cross-cutting theme — a per-season league-settings ledger
- Several findings depend on the same missing artifact: a **per-season record of how the league was
  configured**, because rules changed over time and aren't currently modeled:
  - **Scoring rules** changed across 2010–2015 (F-27) — needed to reconstruct pre-2016 scoring.
  - **Season/week structure** changed (regular 1–13→1–14, playoffs/championship weeks shifted) —
    app-wide (F-32); switch year TBD.
  - **Waiver system** changed standard-order → FAAB at a historical point (F-37); switch TBD.
  - **Ownership succession** — owners changed hands while the 12 teams persisted (F-06); needs
    research.
- Expected: one authoritative, per-season **league-settings ledger** (scoring, schedule, waiver
  system, ownership) — partly auto-discovered (scoring via raw↔nfl.com reconciliation, F-27),
  partly user-supplied (switch years, ownership). Many findings resolve cleanly once it exists.
- This is infrastructure, not a single view fix — call it out in the batch plan as a foundation
  several batches consume.

### Key data fact — raw vs scored coverage split (informs all gap copy)
- `player_stats_raw`: rows for **2010–2025** (every season). Raw NFL stat lines exist for the
  "unscored" era.
- `player_stats_scored`: rows for **2016–2025 only** (season_ids 1, 8–16). Per-player **fantasy
  points** were never reconstructed for 2010–2015.
- Matchup/team totals exist for 2010–2015 (stored from source export), which is why grids/
  standings are complete while box scores are not.
- Implication for fix-passes: the 2010–2015 gap is **player-level fantasy scoring only**.
  Gap copy should say exactly that. A future *reconstruction* (score the raw lines) is a
  **Phase-1 pipeline** job, out of dashboard scope — do not attempt in a dashboard fix-pass.

### Non-finding — 2010–2015 standings are complete by design (not a stale flag)
- The unscored-era probe: `/v1/seasons/2/standings` (2010) returns full `wins/losses/
  points_for/points_against` + `final_rank` for all teams, with season `is_scored:false`.
  `is_scored` flags **player-scoring reconstruction** (no per-player box scores 2010–2015),
  not standings. Standings are correct/complete for those years; the DataGap affordance
  belongs in box-score/player views, not standings. **No action** — recorded so a fix-pass
  doesn't "correct" correct behavior.

---

## Proposed fix passes

Precedent for triage→ship-in-passes: `docs/archive/players-audit-dashboard.md` +
`docs/handoffs/players-audit-danger-zone.md`.

**On batch count.** The ideal is 2–4 batches; this review covered the whole app and surfaced 48
findings spanning every layer, so collapsing to 4 would force mega-PRs that break the
"one coherent slice, gate once" rule. The honest grouping is **6 dashboard passes + 1 upstream
program** (the upstream items are Phase-1 / research, *not* dashboard PRs). Several passes can be
merged or resequenced at the user's discretion; dependencies are noted. Order below is dependency-
first (data/analytics foundations → analytics → views).

### Assignment map (finding → pass)

| Pass | Findings |
|------|----------|
| **P1 — Analytics correctness, scoping & enrichment** (incl. season-structure model) | F-32, F-22, F-31, F-10, F-12, F-23, F-17, F-13 — ✅ resolved by **PR #30** (made_playoffs caveat → F-49/UP) |
| **P2 — Data honesty & affordance precision** | F-16, F-35, F-26, F-33, F-48, F-43 — ✅ resolved by **PR #31**; post-regen redo verified in `docs/archive/fix-P2-post-regen-redo.md` because F-51 changed the coverage premise |
| **P3 — Search (scope, teams, hardening)** | F-44, F-45, F-47 — ✅ resolved by **PR #32** (no contract change; real-DB click-through unblocked by the F-50 regen) |
| **P4 — Transactions (dashboard roster-diff tier)** | F-37 tier 1 — ✅ resolved by **PR #35** |
| **P5 — Frontend: navigation & presentation fixes** | F-34, F-36, F-05, F-24, F-07, F-15, F-46, F-14, F-11, F-40, F-30, F-04, F-28, F-02, F-42 |
| **P6 — Frontend: composition, seasonality & insight enhancements** | F-01, F-29, F-08, F-03, F-09, F-18, F-38, F-21, F-41 |
| **UP — Upstream / Phase-1 program & research** (not dashboard PRs) | F-06, F-25, F-27 (data half ✅ landed → F-51), F-37 (tier 2), F-49, ~~F-50~~ ✅ regen, F-52 |
| **Re-verify (post-regen) — verified** | **F-51** (pre-2016 reconstruction landed → redo P2 honesty verification for F-16/F-26/F-33/F-35 + P1 F-22 scored-window); plan: `docs/archive/fix-P2-post-regen-redo.md` |

---

### P1 — Analytics correctness, scoping & enrichment
- **Scope:** Fix where analytics range over the wrong window or under-surface data; build the
  per-season schedule model that the scoping fixes depend on (ship that first within the pass).
- **Findings:** F-32 (per-season week-structure model + phase filters), F-22 (team/score/season
  records range over **all** seasons with team totals, not just scored era), F-31 (season-totals
  scoped to fantasy weeks only, exclude NFL post-season), F-10 (`made_playoffs` / per-season
  result), F-12 + F-23 (head-to-head enrichment — closest game + cumulative +/-; surface
  `most_lopsided_meeting`/`highest_scoring_meeting` with matchup deep-links in both the
  manager-profile snapshot and the pairwise rivalry page), F-17 (entering W/L record per matchup),
  F-13 (close-game flag, mirror blowout).
- **Files likely touched:** `analytics/standings.py`, `analytics/records.py`, `analytics/stats.py`,
  `analytics/head_to_head.py`, `analytics/matchups.py`, a new season-schedule helper/config; route
  schemas in `api/routes/*` + `api/schemas.py`; `web/src/lib/api/` via `gen:api` (drift check).
- **Signatures (indicative):** `season_schedule(season_year) -> {regular: range, playoffs: range,
  championship: week}`; records era-gating split into `team_record_window()` vs `scored_window()`;
  `head_to_head(...)` adds `closest_meeting{matchup_id}`, `cumulative_margin_for_a`;
  `week_matchups(...)` adds `entering_record` + `is_close`.
- **Tests:** records pick a pre-2016 team game/season when it's the true max; season-totals exclude
  NFL playoff weeks (known-answer); head-to-head closest/cumulative on fixture DB; entering-record
  known answers; phase boundaries per season config.
- **Done when:** team/score/season records computed over the correct window (verified a pre-2016
  game can take a record); season totals = fantasy weeks only; head-to-head enriched + linked;
  entering record + close-game flag present; backend pytest+ruff+mypy green; gen:api drift clean.
- **Depends on:** the season-schedule model (within this pass) — and F-32's switch-years are TBD;
  build the model **config-driven** and seed known values, leave switch-years as user-supplied config.

### P2 — Data honesty & affordance precision
- **Scope:** Stop the honesty layer from over-claiming on complete 2010–2015 data; make pre-2016
  gap copy precise and consistent; add the automated gap-validation harness as the safety net.
- **Findings:** F-16 (decouple gap affordance from season-level `is_scored`; grid/standings/roster
  complete for 2010–2015), F-35 (team roster-by-week over-claim), F-26 (pre-2016-only rostered
  players present honestly, not as empty/error), F-33 (one consistent pre-2016 affordance + copy),
  F-48 (DST gap as dev-facing fact; reconcile `dst_scoring_complete` flag), F-43 (automated
  data-gap / correctness validation harness).
- **Files likely touched:** the `is_scored`→affordance mapping in `web/src/features/{matchups,
  teams,players,stats}/`, shared `DataGap` copy; possibly `is_scored` semantics in meta/analytics;
  new `tests/dashboard/test_coverage_integrity.py` (read-only DB assertions).
- **Tests (the harness itself):** asserts team totals present 2010–2015; player scoring absent
  2010–2015; no never-rostered players in the index; records range over the correct window. Would
  mechanically catch F-16/F-22/F-25/F-31/F-35.
- **Done when:** no view labels complete 2010–2015 team/roster data as incomplete; one warm,
  consistent pre-2016 affordance; harness asserts the coverage truths and is green; gate green.

### P3 — Search (scope, teams, hardening)
- **Scope:** League-scope the search; make team/fantasy-team search work; add functional + security
  tests.
- **Findings:** F-44 (apply the `team_rosters`-scoped filter to the search player branch — never-
  rostered ghosts must not surface), F-45 (NFL team synonyms city/nickname/abbrev; players-by-team;
  fantasy-team-name matching), F-47 (test suite: expected hits/misses + injection/regex/XSS edge cases).
- **Files likely touched:** the search endpoint/query (player + team + fantasy-team branches) under
  `api/routes/` + `analytics/`; `web/src/` search dropdown (scroll, F-46 is in P5); new
  `tests/dashboard/test_search.py`; input-sanitation check in `web/`.
- **Done when:** search returns only league-relevant players; team queries resolve across synonyms
  and surface players-by-team; fantasy team names searchable; injection/regex tests pass; gate green.

### P4 — Transactions (dashboard roster-diff tier)
- **Scope:** Derive in-season transaction activity from `team_rosters` week diffs; separate draft
  from in-season activity on the team page. (nfl.com scrape + FAAB → UP.)
- **Findings:** F-37 tier 1.
- **Files likely touched:** new `analytics/transactions.py` (week-over-week roster diff →
  add/drop/retain), schema + `api/routes/teams.py`, `web/src/features/teams/` transactions section.
- **Signatures:** `derive_transactions(team_id, season) -> [{week, player, action: add|drop|retain}]`.
- **Tests:** roster-diff known answers on fixture DB (added/dropped/retained spans), draft vs
  in-season separation.
- **Done when:** team page shows derived in-season activity distinct from draft picks; tests green;
  gate green. (Exact dates / waiver-vs-FA / FAAB bids deferred to UP.)

### P5 — Frontend: navigation & presentation fixes
- **Scope:** Correctness/navigation bugs and presentation fixes that don't need new analytics.
- **Findings:** F-34 (team season selector wiring), F-36 (unavailable box-score link → degrade
  to team-total view, not error), F-05 (manager→latest-roster link via owner→team hop), F-24 (remove
  `scope=all` + `has_scored` from the players UI/contract), F-07 (sort direction toggle), F-15
  (week selector dropdown/list), F-46 (search dropdown scroll), F-14 (margin +/- green/red), F-11
  ("24g"→clear games label), F-40 (12-column snake draft board), F-30 (stats default = season
  totals), F-04 (playoff placements on completed standings — data already present), F-28 (collapse
  ownership timeline further), F-02 + F-42 (timeline legibility — shared chart wrapper: Week N label,
  rank-ordered tooltip, 12 distinct colors, de-noise).
- **Files likely touched:** `web/src/features/{teams,matchups,managers,players,draft,standings,
  stats,power}/`, the shared chart wrapper, the shared week-stepper; `api/routes/players.py` +
  schema for the F-24 contract change (gen:api drift).
- **Done when:** selectors/links work (incl. pre-2016); scope/has_scored gone; sort toggles; week
  selectable; draft board is a 12-col snake; timelines legible; typecheck+lint+vitest green;
  gen:api drift clean; click-through verified.

### P6 — Frontend: composition, seasonality & insight enhancements
- **Scope:** Re-curate views around season-aware modules and richer insights (the product's reason
  for existing).
- **Findings:** F-01 (home re-curation + season-phase signal), F-29 (player availability →
  insight module, off-season), F-08 (trophy case redesign), F-03 (standings extra insight), F-09
  (manager extra insight), F-18 (richer box-score breakdown), F-38 (draft-value drill-down + sort),
  F-21 (league-wide trophy case in records), F-41 (power: revise/expand methodology, keep the view;
  F-01 still drops power top-movers from home).
- **Files likely touched:** `web/src/features/{home,players,managers,records,draft,power,matchups,
  standings}/`; a shared **season-phase** helper (in-season vs off-season) consumed by F-01/F-29;
  small `analytics/` helpers where a new insight needs a metric.
- **Done when:** home/players/records re-curated and season-phase-aware; new insight modules land;
  power methodology improved + documented; gate green; click-through verified.

### UP — Upstream / Phase-1 program & research (NOT dashboard PRs)
- These are data-origin / research efforts outside the dashboard's read-only scope. Each should be
  its own program with its own plan; dashboard passes consume their outputs.
- **F-27 — Pre-2016 scoring reconstruction** (strategic north star). Discover each pre-2016 season's
  scoring settings by reconciling `player_stats_raw` against definitive nfl.com scores; log a
  per-season scoring-rules ledger; produce `player_stats_scored` for 2010–2015; self-validate. When
  it lands, F-16/F-22-player/F-26/F-39 collapse and the coverage page becomes largely obsolete.
- **F-25 — Roster→player match cleanup.** Automated, self-informing reconciliation of `team_rosters`
  → player identity (remove ghosts like A.B. Brown, fix mis-matches, audit the week-0 artifact).
  Likely mutates pipeline data → `ff_pipeline`, not the dashboard.
- **F-37 tier 2 — nfl.com transactions scrape.** Real transaction log (dates, waiver/FA/trade, FAAB
  bids), incl. the standard-order→FAAB switch.
- **F-06 — Ownership succession research.** Establish the team-line vs owner-tenure history; feeds a
  correct owner identity model.
- **F-49 — `is_consolation` unpopulated → `made_playoffs` not derivable (surfaced by fix-pass P1).**
  Phase-1 sets `Matchup.is_playoff=True` on **every** post-regular-season game (championship *and*
  consolation brackets) but never sets `is_consolation` (0 rows in the real DB; all 12 teams carry
  `is_playoff` games every season). The dashboard's F-10 `made_playoffs` derivation therefore can't
  distinguish a real playoff berth from a toilet-bowl game; it honestly returns `None` for any season
  whose bracket isn't a proper subset of the league (so most seasons read `None` today, a few older
  ones with a distinguishable bracket derive True/False). **UP fix:** populate `is_consolation` (and/or
  a per-season `playoff_teams` count) in `ff_pipeline` so the bracket is distinguishable; once it lands,
  `made_playoffs` becomes derivable league-wide with no dashboard change. The dashboard guard already
  consumes the better data automatically. (`result` is unaffected — it derives from `final_rank`.)
- **F-50 — stale on-disk `fantasy.db` is missing `teams.team_avatar_asset_id` / `owner_avatar_asset_id`
  (surfaced by fix-pass P3 VERIFY). ✅ RESOLVED 2026-06-06 by the DB regen** (the new `fantasy.db`
  carries both columns; app-wide 500s gone, P3 click-through completed). danger-zone (ff-pipeline) advanced to **1.2.0**, adding
  `team_avatar_asset_id` and `owner_avatar_asset_id` to the `teams` table, but the on-disk
  `../danger-zone/data/fantasy.db` was built by an older pipeline and lacks both columns. Any
  full-entity `select(Team)` therefore raises `OperationalError: no such column: teams.team_avatar_asset_id`
  → **HTTP 500**. This breaks the dashboard **app-wide on the real DB**, not just search: confirmed 500
  on `/v1/owners`, `/v1/owners/{id}`, `/v1/seasons`, and `/v1/search`; the offending reads are
  `analytics/search.py:100`, `analytics/owners.py:94`, `analytics/standings.py:67`, `analytics/standings.py:152`.
  Fixture tests don't catch it because the fixture DB is built from the live 1.2.0 ORM (every column
  present). **UP fix (chosen):** regenerate `fantasy.db` with the 1.2.0 pipeline in danger-zone so the
  columns exist; no dashboard code change. Once the DB is regenerated, every full-entity `select(Team)`
  works again and the P3 search click-through can complete. (Considered-and-deferred dashboard
  alternative: narrow each `select(Team)` to explicit columns so the dashboard tolerates an older DB —
  rejected for now in favor of the single upstream regen, to keep the read-only dashboard code uniform.)
- **F-51 — pre-2016 per-player scoring reconstruction has LANDED in the DB → live honesty
  affordances now over-claim a gap that is filled (surfaced by fix-pass P3 VERIFY, 2026-06-06).**
  The regenerated `fantasy.db` now has `player_stats_scored` rows for **2010–2025** (~6,560/yr for
  2010–2015; previously 2016–2025 only), and `/v1/seasons` reports `is_scored:true` for every
  2010–2025 season. This is the **F-27 reconstruction landing** — a major data advance, not a defect.
  **Impact:** the P2 honesty work (merged PR #31) is now *inverted* — the pre-2016 "Per-player scoring
  not reconstructed" banners (F-16/F-35/F-33), the `season_unscored` / `pre2016_unscored_rostered`
  DataGap reasons (F-26), and the season-selector "· no player scoring" label now describe a gap that
  no longer exists, so the dashboard currently **mis-states** pre-2016 coverage. The P1 era-split
  (F-22: team records over 2010–2025, player records over a `scored_window` that was 2016–2025) also
  needs revisiting now that the scored window is 2010–2025. **Action:** a re-verify pass to retire/rework
  the pre-2016 gap affordances and widen the scored window to the data (the affordances already derive
  from `is_scored`/coverage, so much may self-correct — but it must be confirmed end-to-end, and the
  reconstruction's *trustworthiness* should be sanity-checked before we present it as authoritative).
  → resolves the data half of **F-27**; triggers re-verification of F-16/F-26/F-33/F-35 (P2) and F-22 (P1).
  **✅ DASHBOARD HALF RESOLVED by PR #33** (`feature/fix-F51-current-season-scoring`): copy + semantics
  reframe, no gating change (every gate was already data-driven on `is_scored`) — `PRE2016_GAP_NOTE`→
  `UNSCORED_SEASON_NOTE` (year-agnostic, drops the false team-completeness claim); reworded the
  `season_unscored` label; player-detail `pre2016_unscored_rostered`→ generalized data-driven
  `unscored_tenure` (no scored season in the rostered span); reframed About copy; updated `records.py`
  comments + live docs (CLAUDE.md, 03/04/06). Verified on the **real DB** (built SPA): 2026 shows the
  new banner, 2010–2025 show none, About reads "Per-player scoring covers 2010–2025". The data half
  (F-27) and **F-52** remain upstream (UP/danger-zone).
- **F-52 — every season row is `status:in_progress`, including completed 2010–2025 (surfaced by
  fix-pass P3 VERIFY, 2026-06-06).** The regenerated `seasons` table has `status = 'in_progress'` for
  all **17** seasons; only 2026 should be in-progress. Any dashboard logic that keys on season status
  (current-season detection, completed-season framing) will read every historical season as live.
  Likely a pipeline regen artifact (status not finalised). → **UP:** danger-zone should set terminal
  status on completed seasons; re-check any dashboard `status`-dependent rendering once corrected.
  *(Note 2026-06-06: a later regen appears to have fixed this — `/v1/seasons` now reports
  `status:"completed"` for 2010–2025 and `in_progress` only for 2026. Re-confirm on the live DB
  before closing.)*
- **F-53 — `team_rosters` week 1 is a corrupt/placeholder snapshot in every season (surfaced by
  fix-pass P4 VERIFY, 2026-06-06).** On the regenerated `fantasy.db`, for **every** season 2010–2025
  the `week = 1` roster snapshot is disjoint from both its `week = 0` neighbour (the genuine draft /
  opening roster) and its `week = 2` neighbour (the settled in-season roster): player-id overlap is
  **0–7 of 17** across all seasons (e.g. 2010 ROBZILLA `team_id=22`: wk1 ∩ wk0 = 0/17, wk1 ∩ wk2 =
  0/17). The week-1 rows carry the correct `season_year` but reference anachronistic players — a 2010
  team's week 1 lists modern players (Brock Purdy, Bucky Irving), identical to a 2016 team's week 1,
  while that same team's weeks 0 and 2–17 hold genuine 2010 players (Roethlisberger, Joseph Addai).
  **Why the rest of the app doesn't show it:** the existing `/v1/teams/{id}/roster` view renders a
  single week (it defaults to the last available week, e.g. wk17, and its `weeks_available` already
  excludes wk0), so it never surfaces the wk1 anomaly. **fix-pass P4's `derive_roster_moves` is the
  first reader that diffs *all* weeks**, so it faithfully turns the corrupt wk1 into a storm of
  fabricated adds (everyone in wk1) and drops (everyone gone by wk2), plus phantom drop-then-re-add of
  the genuine roster across the wk0→wk1→wk2 gap (e.g. team 184/2024: 68 adds + 67 drops at wk1). The
  dashboard derivation is **logically correct on the input**; the defect is the source data. **Impact:**
  the P4 roster-moves card would render misleading churn for every season → violates the honesty rule;
  P4's real-DB sign-off is **BLOCKED** until the data is corrected (mirrors how F-50 blocked P3). **UP
  fix:** danger-zone should fix the week-1 snapshot ingestion (it looks like a placeholder/seed roster
  written at week 1, or week-0/week-1 indexing being off-by-one with a bad seed). No dashboard code
  change — encoding a "skip week 1" workaround would be a fragile patch over corrupt data and is
  rejected (read-only boundary; stop at the dashboard boundary). Once week 1 is consistent with its
  neighbours, P4 derives correct adds/drops with no code change. **Open question for danger-zone:** is
  week 0 the canonical opening/draft roster (so the fantasy weeks are 0-indexed), or should the opening
  roster live at week 1? P4's derivation treats the first present week as the opening roster either way,
  so it is robust to that choice once wk1 is not corrupt. → **assigned to UP.**
  *(Resolved 2026-06-06: danger-zone regen fixed the wk1 snapshot. Lightweight real-DB recheck
  on `../danger-zone/data/fantasy.db` — for the 12 real franchises, wk1∩wk2 player-id overlap is
  now **0.71–0.88** of the roster across every season 2010–2025 (was 0–7/17), and wk1 holds
  period-correct players (2010 wk1 → Dez Bryant, not Brock Purdy). The "68 adds + 67 drops at wk1"
  fabricated churn is gone; real-team wk0→wk1 churn is now normal post-draft waiver activity. **P4
  unblocked, no dashboard code change.** Residual (separate identity artifact, not this churn
  corruption): 1–2 phantom **week-1-only** teams per season with duplicate/garbled names
  ("JFCFPWCPGAWWLTDOSGT", "Rev Russell's Sunday Service") and ~2 matchups each, present 2010–2018,
  absent in 2019/2023/2025 — relates to the owner/team-identity work, not F-53.)*
- **Foundation both sides need:** the **per-season league-settings ledger** (scoring rules, week
  structure, waiver system, ownership) — see the cross-cutting theme above. P1 builds the schedule
  slice config-driven; UP/F-27 builds the scoring slice; user supplies switch-years and ownership.
