# 04 — Analytics Model

This is the catalog of every **derived metric** Phase 2 computes. It is to Phase 2 what the
scoring engine doc was to Phase 1: the place where ambiguity goes to die. Each metric has a
precise definition so the implementation, the tests, and any future reader agree on what the
number means. **All of these are computed in `ff_dashboard/analytics/`, never in the
frontend.**

Conventions used below:
- "regular season" = weeks `1..seasons.regular_season_weeks` (never hardcoded).
- A "game" = a pairing of two `matchups` rows for the same (season, week). Bye rows
  (`opponent_team_id IS NULL`) are excluded from H2H counts.
- "scored points" = `player_stats_scored.total_points`; "team score" =
  `matchups.team_score` (authoritative team total from Phase 1).
- Metrics that require scored points are computed over the **data-driven scored window**
  (`is_scored` seasons — now **2010–2025** since the pre-2016 reconstruction landed, F-51);
  a season with no scoring yet (normally the current one) falls back to record-only data and
  marks scoring gaps. Never hardcode the window — derive it from `is_scored`.

---

## 0. Season-schedule model (`analytics/season_schedule.py`)

The single place that answers "how is *this* season's calendar shaped?" so no consumer
hardcodes 14/17. `season_schedule(session, season)` → a frozen `SeasonSchedule(season_year,
regular_weeks, playoff_weeks, championship_week, is_estimated)`; helpers `fantasy_week_range`
(weeks `1..championship_week`) and `phase_of_week` (`regular`/`playoff`/`championship`/
`out_of_season`). It is **config-driven**: confirmed historical shapes live in `_CONFIRMED`
(returned `is_estimated=False`); everything else derives from the season's own
`regular_season_weeks` / `playoff_weeks` columns (with the modern 3-week bracket as the
playoff-length default) and is flagged `is_estimated=True`. `_CONFIRMED` is **empty** until the
league's 1-13 → 1-14 season-length switch year is supplied (roadmap input #1), so today every
season resolves to its current DB-derived shape — purely additive, no output change. Consumers:
the records era split, week-capped season totals, and matchup entering-records all read it.

## 1. Standings & records (`analytics/standings.py`)

- **Record (W-L-T)** — count of `matchups.is_win` true/false/null grouped by team, regular
  season only.
- **Points For / Against** — sum of `team_score` / `opponent_score` over regular season.
- **Standings rank** — prefer Phase 1's reconstructed `teams.final_rank` (the NFL.com truth,
  which already bakes in any historical tiebreak we deliberately do not re-derive). Where
  `final_rank` is absent (e.g. an in-progress season), compute wins-desc → points-for-desc.
  The payload exposes `rank_basis` (`final_rank` vs `computed`) and a `tiebreak_caveat` flag
  (true when computed *and* season < 2019). Do **not** re-implement the league's old best-of-3
  tiebreak. (Resolved — see `10_OPEN_QUESTIONS.md` Q5.)
- **Standings through week N** — same, restricted to weeks ≤ N. Used for time-travel and the
  standings-over-time chart (one rank line per team across weeks).
- **Streak** — current/longest W or L run within a season, computed from the week-ordered
  result sequence.
- **Schedule luck / all-play insight** — for each regular-season week, compare every played
  team's score against every other played team's score. `standings_insights()` exposes all-play
  win pct, expected wins, and `luck_delta = actual_wins - expected_wins`. This is team-total
  only and works for any season with matchup scores.
- **Historical divisions (2010–2019)** — `analytics/conferences.py` joins the reviewed
  `data/historical_divisions.json` artifact to `teams.team_abbrev` (NFL.com team ID). Weekly
  W-L-T, PF, PA, Win%, and streak still come from `compute_standings()`; in-division W-L-T counts
  opponent-linked regular-season matchup rows where both teams map to the same source division.
  Midseason division order is the existing weekly overall order filtered into each division.
  At the completed regular-season week, division and overall ranks come directly from NFL.com's
  captured regular-standings ranks. Missing, duplicate, extra, or multi-division mappings return
  `historical_division_mapping_gap`; no partial table is fabricated.

## 2. Power ranking (`analytics/power.py`)

A model-driven ranking distinct from raw standings (rewards strong scoring, not just luck).
**Default model (transparent, explainable — this is not Phase 3 prediction):**

```
power_score = 0.40 * z(points_for_per_game)
            + 0.25 * z(all_play_win_pct)
            + 0.20 * z(win_pct)
            + 0.15 * z(points_for_last_3_weeks_per_game)
```

where `z(...)` is the within-season z-score across teams. Rank by `power_score` desc. The
weights live in one constant and are documented in the UI ("how this is computed"). All-play
uses the same team-total helper as the standings insight, so the model is schedule-luck aware
without depending on player-level scoring. Provide both a current-week power ranking and a
power-ranking-over-time line per team.

> Keep the model simple and legible. The point of the power ranking is to start an argument
> at the bar, not to predict the future — that's Phase 3.

## 3. Matchup / box-score enrichment (`analytics/matchups.py`)

Built on Phase 1's box-score data (`team_rosters` joined to `player_stats_scored`).

- **Per-player league points** — the **authoritative** NFL.com value from each weekly
  roster row's `team_rosters.extra_data.nfl_com_points`. This is what the league actually
  awarded: it exists for every roster row (including players nflverse never logged a stat
  line for — inactive / DNP / bye, who scored a legitimate 0.0), and the starters' values
  sum to `matchups.team_score`. The nflverse `player_stats_scored` reconstruction is only a
  fallback when `nfl_com_points` is absent; a row with neither source is flagged
  (`team_defense_not_scored` / `no_scored_data`), never zeroed.
- **Breakdown** — the per-category stacked chart (passing/rushing/receiving/bonus/… and the
  defense keys for DST) is still passed through from Phase 1's nflverse scored breakdown JSON;
  it is supplementary and may be empty for a player who has an authoritative total but no
  nflverse stat line.
- **Zero-point context** (`classify_zero` → `zero_reason` / `zero_detail`) — a `0.0` is
  explained, not left ambiguous: `"bye"` when the per-week `extra_data.opponent` is `"Bye"`;
  `"did_not_play"` when the team played but the player has no nflverse stat line
  (inactive / injury / scratch); no annotation when a real stat line simply nets ~0 (a clean
  played-0 renders a bare `0`); and `"unexpected"` (with a `zero_detail` note) when the league
  scored 0 yet nflverse credits material points — surfaced rather than shown as a silent 0.
- **Bench points** — sum of scored points for non-starter, non-IR slots.
- **Optimal lineup & "points left on the bench"** — the highest-scoring legal lineup given
  that week's roster and the league's slot configuration (read slot rules from
  `scoring_rules`/roster config). `points_left = optimal_total - actual_starter_total`.
  This is a constrained max-assignment over slots; implement it explicitly and test it.
- **Margin** — `team_score - opponent_score`. Drives the inline signed `+/-` indicator beside
  each team's score on both the weekly grid and the box score; margin alone is **not** a flag.
- **Superlative flags** (`analytics/matchup_flags.py`, on both `week_matchups` *and*
  `box_score`) — a list of `{kind, label, tone, team_id, detail}` per game describing what made
  it memorable, so the grid and the box score never disagree. Thresholds are documented module
  constants; the frontend does **no** math, only renders the list. Kinds: `blowout`
  (`margin >= BLOWOUT_MARGIN`, 40) / `nailbiter` (`margin <= CLOSE_MARGIN`, 5); `season_high` /
  `dud` (a team's score is the season's highest / lowest, byes excluded); `shootout` /
  `cold_snap` (combined score is the season's highest / coldest); `tough_luck` (the loser
  outscored every other team that played that week); `upset` (winner entered with `>=
  UPSET_RECORD_GAP` fewer wins than the loser, after `MIN_ENTERING_GAMES`); `monster_game` (the
  game held one of the season's top-`MONSTER_TOP_N` starter player-weeks). Empty when a game has
  no scores yet. Every rule uses durable data only — **no projections** (coverage is uneven).
- **Entering record** (`week_matchups`) — per side, the team's regular-season W-L-T from weeks
  *before* this week, that season (regular weeks per the season-schedule model; byes excluded).
  Computed in one query per request, folded per team — no N+1.
- **Projection vs actual** — per starter where a `projections` row exists; aggregate "beat
  projection by" per team. Current/recent seasons only.
- **Per-player contribution labels** — player rows also carry team point share, projection
  delta, and a backend `lineup_value` label (`starter_hit`, `starter_miss`, `bench_pop`,
  `neutral`) so the UI can enrich the expandable table without doing metric math.

## 4. Head-to-head & rivalries (`analytics/head_to_head.py`)

Keyed on **owners**, not teams, so it spans renames and seasons.

- **Pairwise all-time record** — for owners A and B, over every regular-season + playoff
  game they played each other: A's wins, B's wins, ties; total games; average margin (signed
  for A); **cumulative margin for A** (signed running total across all meetings, distinct from
  the per-game average); highest-scoring meeting; most lopsided meeting; **closest meeting**
  (smallest |margin|, oriented to A, deep-linkable via `matchup_id`); count of playoff meetings.
- **Rivalry matrix** — the full N×N table of pairwise win pct (A's wins / games), rendered as
  a heatmap. Diagonal is blank. Symmetric pair (A vs B and B vs A) are complementary.
- **"Closest rivalry"** — the pair with the most games and a win pct nearest 0.5 (a
  league-fun stat for the records book).

## 5. Records book / hall of fame (`analytics/records.py`)

Single-season-spanning superlatives. Each returns the value + the (season, week, team/owner,
player) context so the UI can deep-link to the source matchup/player.

- Highest / lowest **team score** in a single week.
- Biggest **blowout** (max margin) and narrowest **win** (min positive margin).
- Highest-scoring **matchup** (sum of both teams).
- Best single-**player** week (max `total_points` for a started player).
- Longest **win streak** and **loss streak** (across seasons, per owner).
- Most **championships**, most **playoff appearances**, most **last-place finishes**.
- Best season **points-for** total; worst.
- **Draft superlatives** — see §7.

**Era split (fix-pass P1 / F-22).** Team/score/margin records — highest/lowest **team score**,
biggest **blowout**, narrowest **win**, highest-scoring **matchup** — are computed over the
**team-record window**: every season that has team totals (any matchup with a non-null
`team_score`, i.e. 2010–2025, reconstructed back to 2010). Only **player**-level records
(best player week) stay scoped to the **scored window** (`player_stats_scored` present,
2016–2025). The payload carries both `scored_era` and `team_record_era` so the UI can be
honest about each record's window. A pre-2016 game can therefore legitimately hold a team
record. `team_record_window()` / `scored_window()` are the two helpers in `records.py`.

## 6. Owners / managers (`analytics/owners.py`)

- **Career aggregate** — seasons played, total W-L-T, total points-for, championships,
  runner-ups, last-places, best finish, average finish. (Phase 1 already has
  `owner_career_aggregates`; extend with finishes/championships from `seasons`.)
- **Season-by-season table** — one row per season: team name that year, record, PF, final
  rank, **made-playoffs** (derived, see below), and a **result** label. `result` is computed
  from the finish for every completed season incl. 2010–2015: `"Champion"` / `"Runner-up"` /
  `"3rd place"` / `"Nth"`, and `null` (a gap, never 0) when the season has no `final_rank` yet.
  `made_playoffs` is **derived from the schedule** (the `teams.made_playoffs` column is
  unpopulated): True iff the team has ≥1 `is_playoff` matchup that is **not** a consolation
  game, `False` when it missed the bracket — but **only for seasons whose bracket is
  distinguishable**: the non-consolation playoff flag must select a *proper subset* of the
  league (`0 < playoff_teams < league_size`). When *no* team or *every* team carries a
  non-consolation playoff game the bracket can't be told apart in the data — notably Phase-1
  currently leaves `is_consolation` unpopulated and flags **every** post-season game
  `is_playoff`, so whole seasons read as "all teams advanced" — and `made_playoffs` is `None`
  (unknown), never a fabricated True/False. (Upstream gap **F-49** → UP: populate
  `is_consolation` so more seasons become derivable. The `result` label is unaffected — it
  comes from `final_rank`.)
- **Trajectory chart** — final rank (inverted axis) or points-for per season across the
  owner's tenure.
- **Trophy case** — championship and podium finishes with year + team name.
- **Consistency** — stdev of weekly team score across the owner's teams (lower = more
  consistent), ranked league-wide and returned on the owner career payload with a best-season
  pointer and stable signature label.

## 7. Draft (`analytics/draft.py`)

Draft picks are `transactions` with `transaction_type='draft'` (Phase 1 design), joined to
the resulting `team_rosters` (`acquisition_type='draft'`, `acquisition_week=0`) and to
season scored totals.

- **Draft board** — round-by-round picks per team for a season (ordered by draft slot/round).
- **Pick value** — for each pick: player's regular-season scored total that season vs the
  positional expectation at that draft slot. **Steal** = high points, late pick; **bust** =
  low points, early pick. Define value as `season_points - expected_points_at_slot`, where
  expected is the league-wide average season points of players taken near that overall pick
  (computed from history). Document the definition in the UI.
- **Best/worst draft picks ever** — top and bottom by pick value, for the records book.

> Draft analytics depend on draft transactions existing in history. If a season's draft
> wasn't captured, the view shows "draft not available for this season" — do not infer.

## 8. Players (`analytics/players.py`)

- **Player insights** — `player_insights()` summarizes best fantasy week, best fantasy-season
  total (capped to the season's fantasy regular-season weeks), rostered league span, and the
  owner who rostered the player most often. Missing scoring facts stay null/gap-labelled rather
  than rendered as zero.

Mostly passthrough of Phase 1 facts, lightly aggregated for charts.

- **Weekly scoring history** — `total_points` per week for a (player, season), plus raw stat
  line; rendered as a line/bar chart. Multi-season view optional.
- **Ownership history** — which league teams owned the player and when (from `team_rosters` /
  `transactions`); a timeline.
- **Top scorers** — Phase 1's `top_scorers` (by season/week/position). Surface directly.
- **Season totals by position** — dashboard-owned in `analytics/stats.py:season_totals`
  (fix-pass P1 / F-31). Sums `total_points` only over **fantasy weeks** (`week <=
  championship_week` from the season-schedule model), so NFL post-season weeks don't inflate a
  player's season line. Same output shape as the old Phase-1 query (no contract change); an
  unscored current/in-progress season returns `[]`, never zero-filled rows. The Phase-1
  `queries.season_totals` is left untouched (read-only cross-repo boundary).
- **Availability (current season only)** — owned/FA/waivers per week from
  `player_availability`; historical seasons render the documented gap.

## 9. Teams (`analytics/teams.py`)

Per-(season, team) rollups feeding the team page.

- **Team overview** — final record/rank, owner, championship/podium flags for that season.
- **Schedule** — week-by-week opponent + result + margin for the team's season.
- **Scoring trend** — the team's points-per-week against the league average that week (the
  line chart).
- **Transactions** — the season's recorded transactions involving the team (passthrough of
  Phase 1's `transactions`, scoped to the team). The current real DB includes dated
  add/drop/waiver/trade/draft/lineup rows; the dashboard surfaces exact dates, direction,
  waiver priority, notes, slot-change `extra_data`, and nullable FAAB where Phase 1 records it.
- **Derived roster moves** (`analytics/transactions.py:derive_roster_moves`) — in-season
  add/drop/retain reconstructed from **week-over-week `team_rosters` diffs** (a player first
  seen after the opening week is an `add`; one that disappears is a `drop`; one drafted at the
  opening week and kept is a `retain`; drop-then-readd is two stints). This is now a fallback
  estimate for seasons/rows where the exact transaction log is absent or incomplete.
  **Not gated on `is_scored`** (roster snapshots predate the scoring reconstruction). A season
  with <2 snapshot weeks returns `available:false` → the UI renders a `DataGap`, never zeros.

## 10. Global search (`analytics/search.py`)

- **Typeahead** — a single ranked result list across owners, teams, players, and seasons for
  a query string, each hit carrying a typed deep-link target. Read-only over the indexed
  Phase 1 tables; no scoring math.

## 11. Coverage (`analytics/coverage.py`)

- **Coverage flags** for `/v1/meta` — `seasons_present`, `seasons_scored`,
  `reconstruction_complete`, `availability_current_season_only`, `dst_scoring_complete` —
  derived from table probes + the latest `pipeline_runs` row. This is what drives every
  `DataGap` affordance in the UI.

## 12. League history (`analytics/league_history.py`)

Turns existing Phase 1 facts into product-facing league context for the museum/archive
surfaces. It **invents no rules or settings** — unavailable or inferred facts are labelled in
the payload (`source`, `certainty`, before/after) so the UI keeps caveats next to affected
data. Five public read models:

- **`league_timeline(session)`** — one row per season: active league size, schedule shape,
  champion, scoring provenance, and a `changes` block with concrete `details[]`. `league_size`
  is the **active standings-backed** team count; inactive/artifact source rows are caveated in
  `changes.details`, never shown as a league-size change.
- **`league_eras(session)`** — derived era groups plus a material change log. Each change keeps
  compatibility booleans and a `details[]` list (`category`, `title`, `summary`, optional
  `before`/`after`, `source`, `certainty`) covering scoring rules, schedule length, roster/RES
  slots, waiver/FAAB, standings tiebreakers, and manager churn.
- **`league_overview(session)`** — high-level command-center summary: span, counts, current
  era, and data caveats.
- **`league_stories(session)`** — backend-computed story cards (dedup games via `_unique_games`
  so a head-to-head is not double-counted).
- **`manager_directory(session)`** — human-manager directory with identity and team-name
  history.

Period-correct labels come from the companion **`analytics/historical_team_names.py`**
(`period_team_name`) — see `03_DATA_ACCESS.md`. All math stays read-only over existing tables;
no scoring is recomputed.

## 13. Postseason bracket (`analytics/bracket.py`)

- **`season_bracket(session, season_id)`** — a **caveated** postseason surface. Phase 1 stores
  matchup rows, not a reliable championship/consolation tree, so this exposes the **proven
  post-regular-season games grouped by week** and labels a game consolation **only when the
  source actually distinguishes it** — it does not infer a bracket tree or a champion path.
  Returns `None` when the season has no post-regular-season games to show. Pairs with the
  `made_playoffs`/`is_consolation` caveat in §5 and `03_DATA_ACCESS.md`.

## League command center (home view — no dedicated module)

The home/command-center view is **composed client-side** from existing endpoints rather than a
single `/v1/home` composite (there is no `analytics/league.py`). The SPA fetches current
standings (`/v1/seasons/{id}/standings`), the records book (`/v1/records`), and the power
ranking (`/v1/seasons/{id}/power`) and arranges them — doing no math, only layout. See
`05_API_CONTRACT.md` and `07_PAGES_AND_VIEWS.md`.

---

## Testing every metric

Each function above gets unit tests against a **small fixture database** with hand-computed
expected answers (see `08_TESTING_STRATEGY.md`). The fixture encodes a few seasons, a known
champion, a known blowout, a known steal-draft-pick, scored DST starters, and at least one
data-gap case (a synthetic unscored season, a genuinely-missing DEF row) so the "honest about gaps"
behavior is tested, not assumed.
