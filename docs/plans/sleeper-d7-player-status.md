# Plan — Sleeper D7: player status

Branch: `feature/sleeper-d7-player-status` (from `dev` @ 4a44ee7, after D6 merged as PR #133).
Sources: `docs/sleeper/00_UPSTREAM_STATE.md` §2/§3/§4/§5, `docs/sleeper/02` D7,
`docs/sleeper/01` (Injury/status row), `docs/sleeper/03` §3.

**Done when (verbatim):** 2026 box scores show injury designations; the status timeline uses
`player_status_asof` (7-day cutoff; older = gap).

## What exists (probed 2026-11-10)

- **Box score + week-scoped team roster** already show nflverse designations:
  `queries.injury_reports_for_week(session, year, week)` → `analytics/injuries.injury_fields()` →
  `InjuryFields {injury_status, injury_body_part, injury_secondary, injury_practice_status}` →
  `web/src/components/InjuryBadge.tsx` (renders only Out/Doubtful/Questionable/Probable).
  `matchups._injury_for_player_cluster` looks across identity twins.
  `matchups._reserve_eligibility_status` builds the IR-slot status from NFL.com roster
  `extra_data.player_status[_label]` → nflverse → slot; `analytics/player_status.should_suppress_status`
  drops a did-not-play status on a player who played.
- **`analytics/player_status.py` already exists** (that NFL.com current-state-drift classifier). The
  `01` layout's "player_status.py CHG" would mix two jobs, so the merge goes in a **new
  `analytics/status_timeline.py`**. The classifier stays as it is and is reused.
- `GET /v1/players/{id}/availability` is the Phase 1 current-season `player_availability` table.
  It is unrelated and stays untouched.
- Upstream: `queries.player_status_asof(session, ids, as_of, max_age_days=7, source="sleeper")
  -> {player_id: PlayerStatusSnapshot}`. Snapshot fields: `as_of_date, injury_status,
  injury_body_part, injury_start_date, practice_participation, depth_chart_position,
  depth_chart_order, nfl_team, status, extra_data{news_updated, practice_description}`.
  Capability key `player_status_daily`: `partial` on NFL.com, `available` on Sleeper.
- **No NFL schedule in the DB** (upstream reads nflverse schedules only inside the normalizer, which
  we can't import). So the dashboard needs its own week → date rule (Decision 2).
- Live DB: 0 `player_status_snapshots`; `player_injury_reports` cover 2010–2025 (2026 comes at
  go-live). Mixed fixture: `v1_players_nfl.json` has real-shape `injury_status` values (e.g. `IR`), but
  no snapshots or 2026 reports are loaded.

## Decisions (defaults taken; flag to the user in the PR)

1. **Box-score source priority.** The nflverse weekly report is the official game status *for that
   week*, so it wins. A Sleeper snapshot is the fallback for a Sleeper-season week with no nflverse
   row for the player: the newest snapshot on or before the week's kickoff (≤7 days old), which is the
   Wednesday capture after the previous week's games. It carries `injury_source='sleeper'` and
   `injury_as_of`. The badge tooltip says "Sleeper, as of <date>". This matches "prefer retroactive
   sources": no game-day capture.
2. **Week → date.** A pure, tested `week_kickoff(year, week) -> date`: week 1 is the Thursday after
   Labor Day (the first Monday of September), plus 7 days per week. Right for every season 2010–2026
   (2010-09-09, 2025-09-04, 2026-09-10). It is a calendar rule, not a data-year literal. It is only
   used to pick the snapshot `as_of` for Sleeper seasons.
3. **Sleeper status vocabulary** maps onto the existing shapes:
   - `Questionable`/`Doubtful`/`Out` → `injury_status` (badge);
   - `IR`/`PUP`/`Sus`/`NA`/`COV`/`DNR` → a roster-type status. It feeds `_reserve_eligibility_status`
     only, exactly like NFL.com `player_status`, and is suppressed for a player who played;
   - `practice_participation` `Full`/`Limited`/`DNP` → `Full`/`Ltd`/`DNP`.

   Unknown values pass through to the timeline but never to the badge.
4. **nflverse absence is not a gap.** The report lists only designated players. Within a season, a
   week ≤ the season's last reported week with no row for the player = "not on report" (a real
   answer). A week after it (or a season with no reports) = gap `reports_not_loaded`.
5. **Sleeper snapshot gap** = `stale_or_missing_snapshot` whenever `player_status_asof` returns nothing
   (no capture within 7 days of that week's kickoff). Legacy seasons have no snapshot column at all
   (`not_on_platform`: the timeline header shows the shared `player_status_daily` note once, not a gap
   per week).

## Backend

`src/ff_dashboard/analytics/status_timeline.py` (pure helpers + session readers):

- `week_kickoff(year: int, week: int) -> date`
- `sleeper_status_fields(snap: PlayerStatusSnapshot | None) -> SleeperStatus` →
  `InjuryFields` + `roster_status: str | None`, `depth_chart: str | None` ("WR2"), `nfl_team`,
  `as_of: date | None`.
- `week_status(session, season, week, player_ids, cluster_members) -> dict[int, MergedStatus]`. This
  is the one merge used by the box score and the team roster: `InjuryFields` +
  `injury_source: 'nflverse'|'sleeper'|None` + `injury_as_of: date|None` + `roster_status`.
- `player_status_timeline(session, player_id, season_year) -> dict | None` (None = unknown player).

Wire-in: `matchups._team_box` and `teams` week roster call `week_status` in place of the direct
`injury_reports_for_week` + `injury_fields`. `_reserve_eligibility_status` takes the Sleeper
`roster_status` after the NFL.com roster fields.

Route: `GET /v1/players/{player_id}/status?season=YYYY` (`api/routes/players.py`) →
`Envelope[PlayerStatusTimeline]`. `season` defaults to the latest played season the player was
rostered in. 404 for an unknown player; an unplayed season gives `available:false,
reason:'season_not_played'`.

Schemas (`api/schemas.py`):
- `StatusEntry {source, as_of, injury_status, injury_body_part, injury_secondary,
  injury_practice_status, roster_status, depth_chart, nfl_team}`
- `StatusWeek {week, kickoff_date, game_report: StatusEntry|null, game_report_gap: str|null,
  snapshot: StatusEntry|null, snapshot_gap: str|null}`
- `PlayerStatusTimeline {player_id, season_year, platform, platform_label, available, reason,
  has_snapshots, snapshot_capability: Capability, is_provisional, latest: StatusEntry|null,
  weeks: [StatusWeek]}`. `latest` = the newest snapshot ≤ today (7-day rule) for an in-progress
  season, else null.
- Box-score / roster player rows gain `injury_source`, `injury_as_of` (nullable).

## Frontend

- `web/src/features/players/StatusTimeline.tsx` on Player detail, with the existing season picker
  pattern. The table has Week · Game status (`InjuryBadge`, or "—" not on report) · Sleeper snapshot
  (date, badge or roster status, depth chart). It uses `DataGap` for gap reasons. The `latest` card
  sits at the top when present. The Sleeper column renders only when `has_snapshots`.
  `is_provisional` → the "subject to change" note.
- `InjuryBadge`: optional `source`/`asOf` props appended to the tooltip only; the label is unchanged.
  Source label + gap copy in `web/src/lib/platform.ts` (no platform literals elsewhere).
- `npm run gen:api` after the schema change; never hand-edit the client.

## Fixture

`tests/sleeper_fixture.build_mixed_era_db` seeds status through upstream's
`normalizer.sleeper_status.status_rows` + upsert (tests only, approved). It uses `v1_players_nfl.json`
on three Wednesdays before weeks 7, 8 and 9 (`week_kickoff − 1`), with one rostered player present only
on the week-7 date (so week 9 is stale → gap). It also adds two 2026 `PlayerInjuryReport` rows (one
overlapping a snapshot player, to prove nflverse wins). The e2e `serve_e2e.py --mixed` picks it up.

## Tests

- **Unit** `tests/test_d7_player_status.py`:
  - `week_kickoff`: 2010 wk1 = 09-09, 2025 wk1 = 09-04, 2026 wk1 = 09-10, 2026 wk9 = 11-05;
  - vocabulary mapping (Q/D/Out → badge; IR/PUP/Sus → roster_status; practice codes; unknown kept off
    the badge);
  - merge priority (nflverse wins; snapshot fallback with source+as_of; played-player suppression);
  - 7-day cutoff: snapshot exactly 7 days before kickoff used, 8 days → gap, after kickoff ignored;
  - nflverse absence: "not on report" ≤ last reported week, `reports_not_loaded` after.
- **Contract** (same file):
  - `/v1/players/{id}/status` on mixed fixture: 2026 player weeks 7–9 incl. the stale gap; legacy
    season `has_snapshots:false` and no snapshot gaps; unknown player 404; unplayed season;
  - 2026 box score shows a Sleeper-sourced badge and the nflverse-wins row;
  - IR-slot Sleeper `IR` status.
- **Parity:** `test_legacy_parity` — legacy box-score/roster goldens differ **only** by the two new
  null-or-`'nflverse'` keys. Regenerate and show the key-only diff; no legacy value moves.
  New route golden under `tests/golden/fixture/`.
- **Web:** `StatusTimeline.test.tsx` (gap, not-on-report, snapshot column hidden on legacy, latest
  card); `InjuryBadge.test.tsx` tooltip source.
- **e2e:** `e2e/sleeper.spec.ts` + Player detail → status section shows a week-9 gap and a badge.

## Done-when checklist

- [ ] 2026 box score shows a designation (nflverse first, Sleeper fallback) on the mixed fixture
- [ ] Timeline uses `player_status_asof` with the 7-day cutoff; stale = `DataGap`
- [ ] Legacy parity: key-only diff; full gate green incl. e2e; forbidden-import grep clean
- [ ] Click-through of Player detail (2026 + a legacy season) and a 2026 box score
- [ ] `PROGRESS.md` + this file's as-built notes updated
