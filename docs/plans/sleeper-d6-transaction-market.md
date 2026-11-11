# Plan — Sleeper D6: transaction market

Branch: `feature/sleeper-d6-transaction-market` (from `dev` @ e6ebdff, after D5 merged as PR #132).
Sources: `docs/sleeper/00_UPSTREAM_STATE.md` §2/§3/§4/§6, `docs/sleeper/02` D6.

**Done when (verbatim):** a 2026 trade shows all its assets; bid wars visible; legacy seasons show the
capability gap for failed bids with the shared copy.

## What exists (probed 2026-11-10)

- `teams.team_transactions`: one row per leg. It drops failed claims (D3) and the counterpart's
  pick/FAAB leg, and the team's own pick/FAAB leg carries `trade_assets`. `teams.team_faab_budget` gives
  the weekly remaining budget from winning bids, with a $100 base (`_FAAB_BASE_BUDGET`) and era detection
  by whether any `faab_bid` exists.
- `aggregation.is_failed_claim` / `is_move` / `pct_of_budget` (D4) have no consumer yet.
- Upstream helpers: `queries.failed_waiver_claims`, `queries.trade_assets`,
  `queries.traded_picks_for_league`.
- Capabilities: `faab_failed_bids`, `trades_with_picks_faab` and `traded_future_picks` are `available`
  on Sleeper (activity: an empty list is a real answer) and `not_on_platform` on NFL.com. Gap copy for
  `faab_failed_bids` / `trades_with_picks_faab` is already in `web/src/lib/platform.ts` (`GAP_COPY`).
- Mixed fixture, 2026:
  - 27 winning + 26 failed `waiver_add` (`failure_reason`, `faab_bid`; contested groups such as wk4
    player 68: `complete:7, failed:4`);
  - one trade: 2 player legs each way + one player-less leg per team, 2027 R2 pick + $7 FAAB;
  - one `traded_picks` row (owner-keyed);
  - `settings_snapshot.settings.waiver_budget = 100`.
  Legacy fixture: 2017 has 3 winning bids and no failed ones.
- Trade legs share no trade id. A trade = the legs with the same (`executed_at`, `effective_week`,
  {team, counterpart}).

## Decisions taken here (flag at PR)

1. **Additive only.** Grouped trades are a new `trades` list on the team-transactions payload; the
   per-leg `transactions` list is unchanged (subset parity). The SPA renders trades from `trades` and
   leaves out `transaction_type == "trade"` legs from the flat feed. That's a presentation filter, not
   math.
2. **A bid war** = a (season, week, player) group of `waiver_add` claims with at least one failed
   claim. The winner is the `complete` claim, or none (every claim failed). `margin` = winning bid −
   highest losing bid, `None` without a winner. A $0 bid is a real bid. A failed claim with no rival
   (e.g. not enough budget) is listed as a failed bid, not as a war.
3. **Season budget:** `settings_snapshot.settings.waiver_budget` when present, else the legacy $100
   base. Spend share uses `pct_of_budget` (None, never 0, when unknown).

## Scope

### BFF

- **`analytics/faab_market.py` (NEW)**
  - `season_faab_market(session, season_id) -> dict | None`:
    `{season_id, season_year, is_faab_era, budget, teams[], top_bids[], bid_wars[],
    failed_bids_capability}`.
    - `teams[]` holds team ref, `spent`, `pct_of_budget`, `winning_bids`, `failed_bids` (None when
      the capability isn't available, never 0), `largest_bid`.
    - `top_bids[]` = the 10 largest winning bids.
    - `bid_wars[]` = `{week, player ref, winner ref|None, winning_bid, bids:[{team ref, bid, won,
      failure_reason}], margin}`, sorted by week then winning bid.
    - Pre-FAAB season → `is_faab_era False`, empty lists. No captured failed bids on the platform →
      `bid_wars` empty and the capability carries the gap.
  - `team_failed_bids(session, team_id) -> list[dict]`: this team's lost claims (week, player, bid,
    reason, winner ref + winning bid when it's a war).
- **`analytics/picks.py` (NEW)**
  - `league_pick_ledger(session) -> dict`: traded future picks from `traded_picks_for_league`
    (franchise league id), each `{pick_season, round, original owner ref, current owner ref,
    previous owner ref|None}` sorted by season, round, original owner.
  - Capability `traded_future_picks` comes from the latest season. An empty list is a real answer on
    Sleeper. When no season has the capability, the list is empty and a capability gap is returned.
  - Owner refs only, no usernames.
- **`analytics/teams.py`**
  - `team_trades(session, team_id) -> list[dict]`: each trade groups its legs into `{executed_at,
    week, counterpart ref, players_in[], players_out[], picks_in[], picks_out[], faab_in, faab_out}`.
    Both sides' pick/FAAB legs reconcile: the team's own leg is the source and the counterpart's is a
    cross-check. Legacy player-only trades group the same way.
  - `team_transactions` gains `trades` and `failed_bids` (the latter only when the capability is
    available, else `[]` + the capability state).
- **Routes**
  - `GET /v1/seasons/{id}/faab-market` (`SeasonFaabMarket`).
  - `GET /v1/league/picks` (`PickLedger`).
  - Team transactions payload: `trades: list[TeamTrade]`, `failed_bids: list[FailedBid]`,
    `failed_bids_capability: Capability`. Cache faab-market per season.
- **Schemas:** `SeasonFaabMarket`, `FaabTeamRow`, `FaabBid`, `BidWar`, `PickLedger`, `PickRow`,
  `TeamTrade`, `FailedBid` (names final at build). Run `npm run gen:api`.

### SPA (presentation only; copy in `lib/platform.ts`)

- **Team page:**
  - a trade card lists every asset (players in/out, picks, FAAB) from `trades`, and trade legs are left
    out of the flat feed;
  - the FAAB section gains "Lost bids" (week, player, your bid vs the winning bid);
  - legacy shows the `CapabilityGap` for `faab_failed_bids` with the shared copy.
- **Stats page:** a new "FAAB market" tab with a spend table (spent, % of budget, wins, losses,
  largest), top bids, and bid-war cards (all bids, winner, margin). Legacy shows the capability gap in
  the bid-wars spot; pre-FAAB seasons show "Waiver priority era" (not a gap).
- **Draft page:** a new "Pick ledger" tab listing traded future picks (original → current owner). When
  it isn't available, the capability gap shows.

## Tests

- **Unit (`tests/test_d6_transaction_market.py`):**
  - mixed 2026: the wk4 player-68 war = winner $7, losing $4, margin 3; every failed claim sits in
    exactly one war or the solo list; spend excludes failed claims; `pct_of_budget` = spent / 100;
  - top bids are winning bids only;
  - the trade: team 17 sees 2 players in/out per the legs, picks_out 2027 R2, faab_in 7; team 18 is the
    mirror, so both sides reconcile;
  - legacy trade grouping (fixture legacy trade, if any) gives players only;
  - pick ledger: one row, owners resolved, sorted;
  - legacy 2017: `is_faab_era`, 3 winning bids, `failed_bids None`, capability `not_on_platform`, no
    wars;
  - pre-FAAB season: `is_faab_era False`;
  - a $0 bid is a real bid;
  - the D3 pending week does not apply here (transactions have no live state), but a 2026 claim in the
    current week is counted, so pin that it is.
- **Contract:** the legacy goldens hold (subset). `DZ_UPDATE_GOLDEN=new` adds the two new routes. Live
  golden 1092/0.
- **Component:** Team (trade card assets, lost bids, legacy gap), Stats (market tab, gap, pre-FAAB),
  Draft (ledger, gap).
- **e2e (`sleeper.spec.ts`):** a 2026 team with the trade shows all assets; Stats → FAAB market shows a
  bid war.

## Files

`src/ff_dashboard/analytics/{faab_market.py, picks.py (new), teams.py}`,
`src/ff_dashboard/api/{schemas.py, routes/seasons.py, routes/league.py (or the league route module),
routes/teams.py}`, `web/src/lib/platform.ts`, `web/src/features/{teams,stats,draft}/*`,
`web/src/lib/api/` (generated), `tests/test_d6_transaction_market.py`, `web/e2e/sleeper.spec.ts`,
`PROGRESS.md`.

## As built (2026-11-10)

- `analytics/faab_market.py`: `season_faab_market`, `team_failed_bids`, `season_budget`, and
  `faab_bid`, now the one bid reader (`teams` re-exports it as `_faab_bid`). `analytics/picks.py`:
  `league_pick_ledger`. `teams.team_trades` + `trades` / `failed_bids` / `failed_bids_capability` on
  team transactions. Routes `GET /v1/seasons/{id}/faab-market` (cached per season) and
  `GET /v1/league/picks`.
- **Deviation: no Draft "tab".** The pick ledger is a league-wide card at the bottom of Draft
  (`PickLedgerCard`), not a tab: the existing Draft tabs are per-season board lenses.
- Team page:
  - trades render once (`tradeSummaryText`: "Got … · gave …") and their legs are left out of the feed;
  - a "Lost bids" card (FAAB seasons only) goes through `CapabilityGate`, so legacy shows "NFL.com
    didn't record unsuccessful waiver bids." The page reads the season's platform from `useSeasons`
    (the team payload has none), so `team.test.tsx` now mocks `SeasonContext`.
- Stats: a "FAAB market" tab (`features/stats/FaabMarket.tsx`) with spend, biggest bids and bid-war
  cards; "Waiver priority era" for pre-FAAB seasons.
- Real legacy trade legs always carry `direction` in/out and a counterpart (checked on the live DB,
  2010–2025), so grouped legacy trades keep every player.
- Goldens: `/faab-market` added to the season matrix and `/v1/league/picks` to the global paths;
  fixture goldens written for the new URLs only (`DZ_UPDATE_GOLDEN=new`). Live golden unchanged at
  1092/0.
- **Open:**
  - the market's `pct_of_budget` uses the base budget and ignores mid-season credits (the 2022 refund
    the Team budget card handles), so a credited team can read above 100%;
  - `is_move` (D4) still has no consumer.
- **Gate:**
  - pytest green (D6 11 + parity), ruff + mypy clean, write-check empty;
  - contract no drift, Prettier + tsc clean, vitest 244, e2e 20/20;
  - live 2025 FAAB market click-through done.
