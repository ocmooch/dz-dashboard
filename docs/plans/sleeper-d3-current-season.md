# Sleeper D3: current-season experience (plan)

Scope: `docs/sleeper/02` §D3; `01` §3.2 (`BoxScore`, `GET /v1/seasons/current`) and §7; hotspot rows
in `00` §6 marked D3. Built on the mixed-era fixture (`tests/sleeper_fixture.py`); the live DB has
no 2026 data until the go-live (user-approved, upstream).

**Done when (verbatim):** the 2026 season is browsable end to end with the same look as 2025.

## What the fixture shows today (probed 2026-11-10, before any D3 code)

The 2026 fixture season has weeks 1–8 finalized and **week 9 provisional** (`finalized=false`,
`is_win NULL`, live scores on both sides). Against it, the current BFF:

- **Standings** count week 9 as a **tie** (`_result` returns "T" when both scores exist and `is_win`
  is NULL): records read 7-1-1, the streak shows `T`, and PF/PA include the live scores.
  `through_week` reads 14 (the schedule length), not 8.
- **Week matchups** (`/weeks/9/matchups`) name a `winner_team_id` / `is_winner` from live scores.
- `/v1/meta` already returns `current_season_id=5, current_week=9` (D1).
- Transactions include 26 `status='failed'` claims and 2 player-less `trade` legs; 777 roster rows
  carry `slot_certainty='bench_or_reserve'`.
- The fixture has **no idle postseason rows**. Tests add them to a temp copy (as D2's scored copy
  does): opponent-less rows with `postseason_role='bye'|'placed'` and a real score.

## Design

### 1. One game-state rule, shared: `analytics/game_state.py` (new, pure)

```python
def is_game(m) -> bool              # has an opponent (idle postseason rows are not games)
def is_provisional(m) -> bool       # extra_data.finalized is False (legacy rows: never)
def is_final_game(m) -> bool        # is_game and not provisional
def game_result(m) -> "W"|"L"|"T"|None   # only for a final game; replaces standings._result
def official_score(m) -> {"official": float|None, "custom": float|None}   # commissioner override
```

Legacy rows have no `finalized` key, so they are always final: legacy output stays identical (the
golden parity tests prove it). Every D3 surface below uses these instead of reading `is_win` /
`opponent_team_id` / score differences itself.

### 2. BFF surfaces

| Surface | Change |
|---|---|
| `standings.compute_standings` | W-L-T, PF/PA and streak from final games only. New row fields `live_points_for: float\|None` and `provisional: bool`; payload `through_week` = last finalized week, new `live_week: int\|None`. Mirrors upstream `standings_for_season` (S8-D3). |
| `standings` timeline / insights | stop at the last finalized week |
| `matchups.week_matchups` | provisional game: `winner_team_id` null, `is_winner` false on both sides, new game field `provisional: true`, `margin` null. Idle postseason rows are not listed as games. |
| `matchups.box_score` | `provisional: bool`; `winner_team_id`/`margin` null while provisional; new `official_points_source: "nfl_com"\|"sleeper"` (from `season_platform`); new `commissioner_override: {official, custom} \| null` when `custom_points` is set. Each side's `total_score` stays the league score (custom when overridden). |
| `teams` schedule / scoring trend | provisional week shown as current state (no W/L); idle rows skipped as games, their points not counted as PF |
| `teams.transactions_for_team` (L392, L589) | failed claims leave the default activity list and counts; they come back as `status: "failed"` rows only where a view asks for them (D6 builds bid wars). Player-less trade legs render as a pick/FAAB line, not a broken player row. |
| `records` | the in-progress season counts **completed weeks only**; a provisional week never sets a record (blowout, high score, best player week). |
| `head_to_head` | `margin = team_score - opponent_score` only for final games (00 §6). Wider cross-era aggregation (careers, rivalries, power) stays D4. |
| new `analytics/current_season.py` + `GET /v1/seasons/current` | `{season_id, season_year, platform, platform_label, current_week, week_state: "provisional"\|"final", last_finalized_week, matchups: [WeekGame], standings_top: [...], data_as_of}`; `available:false` with reason `no_current_season` when nothing is in progress (never a fake week). Reuses `week_matchups` + `compute_standings`; adds no new math. |

Roster rows with `slot_certainty='bench_or_reserve'` keep `BN` and get a `slot_note` (box score,
team roster) so "bench or reserve" is shown, not hidden. That is a per-row flag; no math.

Out of scope (later milestones): official brackets, divisions and potential points (D5); FAAB market
and failed-bid views (D6); player status (D7); career/rivalry/power era-awareness (D4).

### 3. Frontend (presentation only; no math in `web/`)

- **Home**: when `/v1/seasons/current` is available, a "This week" command-center block at the top:
  week label plus a provisional badge, that week's games as `GameCard`s linking to the box score, and
  the top of the live standings. Off-season keeps today's Home unchanged (`seasonPhase.ts` already
  keys on `status`).
- **`DataAsOf.tsx`**: append "Week N (provisional)" or "Week N final" from `meta.current_week` plus
  the `/current` week state.
- **Matchups / Box score**: a `provisional` badge ("Live: subject to change"); no winner styling
  while provisional; a commissioner-override note (official vs awarded score) via `ProvenanceNote`;
  the points-source footnote reads the label from `lib/platform.ts`, never a literal.
- **Standings**: "through week N" plus a live column or row note for the provisional week.
- **Team transactions**: player-less trade legs show "Draft pick / FAAB" text.

Every platform-specific string goes through `lib/platform.ts` (the `02` per-PR checklist rule; no
CI lint enforces it yet, so review for literals).

## Files

- New: `src/ff_dashboard/analytics/game_state.py`, `analytics/current_season.py`,
  `api/routes/` (`/v1/seasons/current` with the season routes), `tests/test_d3_game_state.py`,
  `tests/test_d3_current_season.py`, `web/src/features/home/ThisWeek.tsx` (+ test).
- Changed: `analytics/standings.py`, `matchups.py`, `teams.py`, `records.py`, `head_to_head.py`;
  `api/schemas.py` (`BoxScore`, `WeekGame`, standings row/payload, `CurrentSeason`); `web/` Home,
  `DataAsOf.tsx`, Matchups/Box score, Standings, Team transactions; regenerated client.

## Tests

Unit (`test_d3_game_state.py`):
- legacy row → final; `finalized=false` → provisional, never a result; no opponent → not a game;
  `custom_points` → override with both values.

BFF on the mixed fixture (`test_d3_current_season.py`):
- 2026 standings: records from weeks 1–8 only (no ties from week 9); `through_week=8`, `live_week=9`;
  `live_points_for` set; streak unaffected by week 9.
- `/weeks/9/matchups`: every game `provisional`, no winner; weeks 1–8 unchanged.
- Box score for a week-9 game: `provisional`, no winner/margin; for the override game,
  `commissioner_override={official:112.46, custom:117.46}`; `official_points_source="sleeper"`;
  same top-level keys as a legacy box score (structure mirror).
- Records: no 2026 week-9 value ever wins a record (raise a live score in a temp copy to prove it).
- Idle postseason rows (temp copy): not in week matchups, schedule, h2h or PF.
- Team transactions: failed claims absent from the default list; pick/FAAB legs present, no crash.
- `/v1/seasons/current`: week 9 provisional, 6 games; `available:false` on the legacy-only fixture.
- Both golden parity tests green (legacy unchanged).

Frontend: Home `ThisWeek` renders provisional and final states and is absent off-season; Box score
provisional badge and override note; component tests with fixture payloads.

e2e: journey "Home → this week's matchup → box score" on the mixed fixture (the VERIFY session).

## Open question for the user (ask in BUILD, before records work)

- Records "include in-progress seasons only for completed weeks, labelled" (`01` §7): label the
  record itself ("2026, through week 8") or a single note on the page? Default: a per-record label
  when the record comes from the in-progress season.
