# 00 — Upstream state for the Sleeper-era dashboard work (read this first)

**Written 2026-11-09, after danger-zone S1–S8 merged** (`danger-zone` `dev` @ 29c9764); §1 go-live
updated 2026-11-10 after S9 merged (`dev` @ f84f502). This is
what the pipeline *actually* delivers, as opposed to what `01`–`03` (planned before the pipeline
work) assumed. Where they differ, **this doc wins**; the corrections are also applied in place.
Read it once per D-milestone PLAN session instead of re-exploring danger-zone.

Upstream references, by section only: `../danger-zone/docs/sleeper/04_SLEEPER_FIELD_MAPPING.md`
(field meaning), `../danger-zone/docs/06_API_CONTRACT.md` (Phase 1 API), plans
`../danger-zone/docs/plans/S5…S8-*.md` (decisions, with the user's wording).

---

## 1. Where the data is (the big gating fact)

- **The live `fantasy.db` has no 2026 league data yet.** The season row exists
  (`season_id 17`, `platform='sleeper'`, `status='in_progress'`), with 12 owners mapped to Sleeper
  users and the old NFL.com 2026 stub quarantined. There are no 2026 teams, matchups, rosters,
  transactions, rules or scores. `played_season_ids()` therefore hides 2026 today.
- **The 2026 go-live is one approved upstream sequence (S5-D1, S6-D1, S7-D1; S9 command)**, run
  when the dashboard is ready (danger-zone `docs/RUNBOOK.md` "Sleeper era operations (S9)"):
  1. `ff-pipeline migrate up` (adds the guard v2 triggers; inert until a Sleeper season is sealed);
  2. `ff-pipeline sleeper-league rules --diff 2025`, then `rules --write`;
  3. `ff-pipeline sleeper-league update`, which runs load → `adopt-gsis --apply` →
     `injury-reports` → nflverse → team_defense → `sleeper-league stats` → `rules --check` →
     rescore → reconcile;
  4. set `SLEEPER_AUTO_LOAD=true` in danger-zone's `.env`.

  It is danger-zone's to run and **the user approves it**; dashboard sessions never trigger it.
- **After step 4, 2026 data changes every Wednesday on its own**: the 06:00 ET weekly job runs
  capture → `sleeper-league update` → full `legacy verify`, then the 07:00 vault sync backs it up.
  Both run released danger-zone code (`main`, from `~/danger-zone-main`), not `dev` (see
  `docs/PHASE2_RUNBOOK.md` "After each danger-zone release"). If the league's scoring settings
  change, `update` stops before rescoring until the user signs off the new rules.
- **The moment it runs, 2026 becomes the dashboard's default season** (latest played season), in
  every view at once. So:
  - **D0 (legacy golden snapshots from the live DB) must be taken before the go-live.**
  - The go-live should wait until at least D1–D3 handle 2026 rows (see §6 for what breaks
    otherwise).
- Until then, **develop against a DB copy**. Upstream keeps fully loaded 2026 copies (a
  rebuildable recipe is in §7). Real weekly captures keep arriving in the live archive
  (`source_payloads`, raw files) every Wednesday 06:00 ET, after the week's games.
- The weekly capture also downloads Sleeper avatars into the shared asset store (live `assets`
  rows of kinds `owner_avatar` / `team_avatar` / `league_avatar`). They are linked to teams only at
  load.

## 2. The read surface (danger-zone S8, `ff_pipeline.repository.queries`)

All are read-only and re-exported from `queries` (the allowed import surface). The implementation
is in `repository/platform_reads.py`.

| Helper | Notes |
|---|---|
| `official_slot_points_expr(roster)` | `coalesce(platform_points, nfl_com_points)` (Float) |
| `authoritative_week_points_expr(roster, scored)` | `coalesce(official, scored.total_points)`. **Proven identical** to `analytics/scoring.authoritative_week_points` on all 49,401 legacy roster rows of the live DB (0 differ). D2 is an alias swap. |
| `season_platform(s, season_id)` | `PlatformInfo(platform, label)`: `nfl_com`/"NFL.com", `sleeper`/"Sleeper" |
| `season_freshness(s, season_id)` | `SeasonFreshness(is_final, last_finalized_week, provisional_weeks)`. NFL.com seasons are always final. A Sleeper week is provisional while `matchups.extra_data.finalized` is false. |
| `season_capabilities(s, season_id)` | `{key: Capability(state, note)}`, see §3 |
| `brackets_for_season(s, season_id)` | `playoff_brackets` rows (Sleeper only) |
| `traded_picks_for_league(s, league_id, pick_season=None)` | current owner of each traded future pick |
| `player_status_asof(s, player_ids, as_of, max_age_days=7)` | newest Sleeper snapshot ≤ `as_of`, not older than 7 days, else absent (a gap) |
| `failed_waiver_claims(s, season_id, team_id=, week=)` | `status='failed'` claims |
| `trade_assets(s, season_id)` | player-less pick/FAAB trade legs |
| `standings_for_season` (changed) | finalized games only; the in-progress week is `live_week` / `live_points_for`, and rows carry `provisional`. Opponent-less rows are skipped. Legacy output is identical (all 16 seasons checked). |

The Phase 1 API (`ff_pipeline.api`, not used by the dashboard) gained the same fields plus
`/seasons/{id}/brackets`, `/leagues/{id}/traded-picks` and `/players/{id}/status`. The
dashboard's own `/v1` contract is unaffected until a D-milestone adds to it.

## 3. Capability matrix (what `season_capabilities` really returns)

States: `available`, `partial`, `derived` (not stored; the dashboard computes it), `not_yet`
(active season, not produced yet), `not_on_platform`, **`not_used`**. The field is **`note`**
(not `reason`, as `01` §3.2 first said).

The user's rules (S8 decisions, 2026-11-09):

- **`not_used` resolves silently**: it has no note, and the UI renders *nothing* (no "no divisions
  this season" text, no `DataGap`).
- **Activity** features (`trades_with_picks_faab`, `traded_future_picks`, `faab_failed_bids`) are
  `available` on Sleeper even with zero events: an empty list is a real answer.
- **League-structure** features (`co_owners`, `commissioner_score_overrides`,
  `official_divisions`) are `available` only when present, else `not_used`.
- **While a season is active**, every representation shows the current state and marks it as
  subject to change. At season end it is static.
- **The unfinished week is unscored (user, 2026-11-10).** A week the capture hasn't finalized
  (`matchups.extra_data.finalized` false) is not a game result in progress: it is never a tie,
  shows no live scores, and adds nothing to standings, PF/PA, records or h2h. It joins the
  dashboard once the weekly capture resolves it. Only its pairings show, marked "awaiting final".

Today's real values: 2025 (NFL.com) =
- `available`: standings, matchups, rosters, draft, official and reconstructed points, moves,
  FAAB winning bids, lineup and setting logs, avatars;
- `derived`: brackets, potential points;
- `not_used`: divisions;
- `not_on_platform`: failed bids, picks/FAAB trades, traded picks, co-owners, overrides;
- `partial`: player status (nflverse weekly reports), availability.

2026 (Sleeper, loaded copy) = core data `available`, reconstructed points `available` after the
rescore, `lineup_change_log` / `setting_change_log` `not_on_platform`, brackets `available`,
divisions `not_used`, co-owners `not_used`, potential points `available` (official `ppts`).

## 4. What 2026 rows look like (shapes the dashboard will meet)

**seasons:**
- `platform='sleeper'`, `regular_season_weeks=14`, `playoff_weeks=3` (weeks 15–17);
- `settings_snapshot` holds the settings, roster positions, scoring settings and draft settings
  (no league name);
- `champion_team_id` / `runner_up_team_id` / `last_place_team_id` are set as the bracket decides
  them. The Sacko = 12th place, known after week 16.

**teams (12):**
- `platform_team_key='sleeper:roster:<n>'`;
- `team_name` from Sleeper, with the fallback `"<owner display name>'s Team"`;
- **`team_abbrev` = the owner's latest legacy abbreviation**, so lineage logic keeps working;
- `draft_position`; `division` NULL;
- `final_rank` = `playoff_finish` = bracket place 1–12 (once decided);
- `made_playoffs` true/false once the regular season is final (legacy rows have NULL);
- `extra_data = {ppts, streak, record_string, waiver_position, waiver_budget_used, total_moves,
  as_of_week, co_owner_user_ids?}`. These are Sleeper's current values, not history.
- Avatar ids are linked when the capture has downloaded them (owner avatars are new; the
  dashboard's avatar route serves team avatars today).

**matchups:**
- `extra_data = {points_official, finalized, sleeper_matchup_id, custom_points?, postseason_role?}`;
- **Provisional week**: `finalized=false`, `is_win NULL`, both scores set (live).
- **Commissioner override**: `team_score = custom_points`, with `points_official` kept.
- **Postseason** follows the legacy convention: every bracket game `is_playoff`; losers-bracket
  games also `is_consolation`; the 3rd- and 5th-place games are not consolation.
- **Idle postseason team-weeks exist** (4 in week 15 = byes, 4 in week 17 = already placed):
  `opponent_team_id NULL`, `is_win NULL`, `is_playoff=false`, `postseason_role='bye'|'placed'`,
  and a real score. Legacy has no such rows.

**team_rosters:**
- one row per player per week; `roster_slot` uses the legacy vocabulary (`QB RB WR TE R/W/T W/R
  W/T Q/R/W/T K DEF BN RES TAXI`, IDP `DL LB DB IDP_FLEX`);
- `extra_data = {snapshot_kind:'sleeper_matchup', platform_slot, platform_points}`;
- weeks with no archived IR list put non-starters in `BN` with
  `slot_certainty='bench_or_reserve'` (an honest flag: weeks 1–8 of 2026);
- week 0 = draft snapshot (`snapshot_kind:'draft'`).
- **No `nfl_com_points`** on these rows.

**transactions:** every row is kept (the user's D4: richer data; consumers must look at
`status` / `player_id`):
- `waiver_add` with `extra_data.faab_bid`;
- **`status='failed'`** = a lost claim (`faab_bid`, `failure_reason`, `intended_drops`; no drop
  leg). Legacy rows have `status NULL`;
- `free_agent_add` / `drop`;
- commissioner moves are `free_agent_add` / `drop` with `extra_data.by_commissioner=true` (**not**
  a `commissioner_move` type, as `03` §4 assumed);
- `trade` in/out legs per player with `counterpart_team_id`, **plus one player-less `trade` leg
  per team that moved picks/FAAB** (`player_id NULL`, `extra_data={picks_in, picks_out, faab_in,
  faab_out}`);
- `draft` rows (`effective_week=0`, notes in the legacy format);
- no `lineup_change` / `setting_change` rows.

**Other tables:**
- `playoff_brackets`: one row per (bracket, round, match), with teams, winner/loser and
  `placement` (`p`). Pre-generated with the current seeds before week 15.
- `traded_picks`: none yet (no 2026 trades so far).
- `player_status_snapshots`: league-referenced players, one row per weekly capture day (Wednesday,
  after the games).
- `player_injury_reports` (nflverse, per week official game status Out/Doubtful/Questionable) now
  cover **2010–2025**, and 2026 at go-live. The `03` §3 copy "No injury reports are available for
  2025" is wrong.

**Points and scores:**
- Official = `platform_points`.
- Reconstructed = `player_stats_scored` with the 2026 rules (all 2025 rules identical, plus 7 new
  Sleeper rules: 40+ yd plays, blocked kicks, defensive 2-pt, ST fumble recoveries, fumble-return
  TD).
- The reconcile matches Sleeper on 1,550 / 1,551 rostered player-weeks.
- `is_scored` becomes true for 2026 after the go-live rescore.

**Players:**
- 26 rookies were split into two rows (a pre-draft Sleeper row and an nflverse row). They are
  merged by giving the rostered row the real gsis id; the empty twin stays, with gsis NULL, linked
  via `player_identity_links` (`source='gsis_adoption'`). The twin has no rosters or stats; the
  `rostered_ever` filter hides it.

## 5. Decisions already made with the user (don't re-ask)

- Capability rules as in §3 (silent `not_used`, activity vs structure, current state while active).
- Include rich data, don't hide it: failed claims, pick/FAAB legs, non-primary Sleeper stats
  (`player_stats_raw.source='sleeper'`, never scored). The dashboard decides what to surface.
- Postseason flags follow the legacy convention. Idle postseason rows are kept (their points are
  real).
- Player status: weekly post-games snapshots plus nflverse weekly reports. No game-day capture (the
  user prefers retroactive data to time-critical jobs).
- Never commit league team/owner names or Sleeper usernames (public repos). Upstream fixtures are
  pseudonymized (ids in the `9000…` range).

## 6. Dashboard hotspots that will misbehave on 2026 rows (found 2026-11-09)

| Where | What happens with 2026 data | Milestone |
|---|---|---|
| `analytics/head_to_head.py` (~L95–106) | decides a game by `team_score - opponent_score`, so a provisional week counts as a live win/loss | D3 / D4 |
| `analytics/standings.py` `_result(...)` | `is_win NULL` with both scores reads as a tie or result: the provisional week | D3 |
| any consumer of `matchups.opponent_team_id` (records, bracket, conferences, matchup_flags, head_to_head, standings, power, league_history, matchups, owners, teams) | idle postseason rows have no opponent: skip them as non-games; don't count their points as PF | D3 / D5 |
| `analytics/bracket.postseason_classification` | derives from connectivity; for 2026, prefer `brackets_for_season` (official). The legacy path stays. | D5 |
| `analytics/transactions.py`, `teams.py` (`transactions_for_team` L392, L589), `draft.py`, `league_changes.py`, `coverage.py`, `matchups.py` | will meet `status='failed'` claims and player-less trade legs. FAAB spend, activity counts and add/drop lists must exclude failed claims unless showing bid wars, and handle `player_id NULL`. | D3 / D6 |
| `analytics/scoring.py` + direct `nfl_com_points` reads in `players.py` (~L133), `matchups.py` (~L140), `records.py` (~L213) | 2026 rows have no `nfl_com_points`, so official points vanish | **D2** |
| `analytics/common.played_season_ids` | 2026 appears and becomes the default as soon as the go-live loads matchups | sequencing (§1) |
| owner avatars | new `owner_avatar_asset_id` links; today's route serves team avatars | D1 / D8 |

## 7. Test fixtures without surprises

- Upstream has **pseudonymized real-shape Sleeper fixtures**:
  `../danger-zone/tests/fixtures/sleeper_league/season_2026/` (league, users, rosters, matchups
  1–9, transactions, draft, brackets, players, weekly stats) plus `synthetic/` (a trade with a pick
  and FAAB, a co-owner, a commissioner override, a traded pick).
- danger-zone's tests build a **mixed-era DB** from them: a sealed NFL.com season + an open
  NFL.com season + the 2026 Sleeper load (`tests/integration/test_sleeper_load.py` `_prepare` /
  `_load`, `test_sleeper_rich.py` `_decided` for a fully decided 6+6 bracket). A dashboard test
  fixture can reuse that path: it runs `ff_pipeline` loaders **inside tests only**. The
  forbidden-import grep covers `src/ff_dashboard`, not `tests/`. **Approved by the user
  (2026-11-09): tests may use the pipeline's loaders** to build the mixed-era fixture. `src/` stays
  read-only.
- A full 2026 DB copy: copy the live DB, then run the go-live sequence (§1) against the copy
  (`DATABASE_URL=sqlite:///<copy>`). About 2 minutes, needs network for nflverse.
