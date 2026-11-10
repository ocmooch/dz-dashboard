# 01 — dz-dashboard Architecture for Mixed-Platform History

**Status:** planned, not started · corrected 2026-11-09 against the delivered pipeline (S1–S8): **read `00_UPSTREAM_STATE.md` first; it wins where they differ** · **Repo:** `dz-dashboard` (Phase 2)
**Program plan (canonical):** `../danger-zone/docs/sleeper/00_SLEEPER_ERA_MASTER_PLAN.md`
**Companions:** `02_DASHBOARD_BUILD_PLAN.md` (milestones D0–D8), `03_CROSS_PLATFORM_UX.md` (UX rules)
**Upstream detail:** `../danger-zone/docs/sleeper/01_PIPELINE_ARCHITECTURE.md` §5 (schema), §8.3 (capabilities), §9.1 (read helpers)

---

## 1. Scope

From 2026 the league plays on Sleeper. The dashboard must show 2010–2025 (NFL.com) and 2026→
(Sleeper) as **one league history**: same pages, same visual language, aggregates that span both,
honest gaps where a platform lacks a fact, and new surfaces for facts only Sleeper provides.

The Phase 2 boundaries do not change: the dashboard never writes the DB, never calls Sleeper or
its CDN, and keeps all math in `analytics/`. Upstream does the ingestion; the dashboard reads the
same canonical tables it reads today.

## 2. Principles

1. **Platform is provenance, not presentation.** A season *has* a platform; pages are not
   *organized* by platform. There is no "Sleeper section".
2. **Render from capabilities, never from platform names.** The BFF tells the SPA what each season
   can show (`capabilities`). The SPA never branches on `platform === "sleeper"` for behavior; the
   platform string is used for labels only.
3. **One visual language.** Same tokens, primitives, number formats and slot labels for both eras.
   The only platform-visible element is a small, consistent era marker (see `03_CROSS_PLATFORM_UX.md`).
4. **Era-aware aggregation lives in `analytics/`.** Any metric spanning seasons states, in its
   payload, which capabilities it relied on and which seasons it excluded or normalized.
5. **Legacy parity is a test, not a hope.** Every existing endpoint returns byte-identical payloads
   for 2010–2025 before and after this program (golden snapshot tests), except for the explicitly
   additive fields.
6. **Gaps are per capability, with a reason code.** "Lineup-change history isn't available from
   Sleeper" and "Official brackets weren't recorded by NFL.com" are the same affordance
   (`DataGap`) with different reasons.

## 3. How the seam changes

### 3.1 Python reuse seam (BFF ⇄ `ff_pipeline`)

| Today | After |
|-------|-------|
| `analytics/scoring.py` defines `nfl_com_points()` and `authoritative_week_points()` over `team_rosters.extra_data.nfl_com_points` | Delegates to upstream `queries.official_slot_points_expr()` / `authoritative_week_points_expr()`, which coalesce Sleeper `platform_points` with `nfl_com_points`. The local names stay as thin aliases so call sites don't churn. |
| Imports `seasons, teams, matchups, team_rosters, transactions, …` | Plus `owner_platform_identities`, `playoff_brackets`, `traded_picks`, `player_status_snapshots` (read-only) |
| No platform concept | `queries.season_platform()` / `season_capabilities()` |

Both changes stay inside the existing rule: "only `ff_pipeline.repository` + pure scoring helpers".

### 3.2 HTTP contract seam (SPA ⇄ BFF) — additive

| Schema / endpoint | Addition |
|-------------------|----------|
| `SeasonListItem`, `SeasonSummary`, `LeagueTimelineSeason` | `platform: "nfl_com" \| "sleeper"`, `platform_label: str`, `capabilities: SeasonCapabilities` |
| new `SeasonCapabilities` | `{ <capability_key>: { state: "available" \| "partial" \| "derived" \| "not_on_platform" \| "not_yet" \| "not_used", note: str \| null } }` — mirrors upstream `season_capabilities` (`00` §3; `not_used` renders nothing) |
| `MetaResponse` | `platform_eras: [{platform, label, start_year, end_year \| null}]`, `current_season_id`, `current_week` |
| `CoverageMatrix` | a `platform` column per season row; capability cells beside feed cells |
| `LeagueEras` (existing rules/playstyle eras) | the platform switch is emitted as a `LeagueEraChange` ("Moved to Sleeper") so it appears in the existing Timeline without a new concept |
| `ManagerIdentity` | `platform_accounts: [{platform, display_name, first_season, last_season}]` (no raw user IDs) |
| `BoxScore` | `official_points_source`, `commissioner_override: {official, custom} \| null` |
| `TeamOverview` / `Standings` rows | `division` (official when present), `potential_points` + `potential_points_source: "official" \| "computed"` |
| new `GET /v1/seasons/{id}/brackets` | official winners/losers brackets with placements; falls back to today's derived `/bracket` shape for legacy seasons |
| new `GET /v1/seasons/{id}/faab-market` | winning and failed bids, bid wars, price per position |
| new `GET /v1/league/picks` | traded future picks ledger |
| new `GET /v1/players/{id}/status` | dated injury/practice/depth snapshots |
| new `GET /v1/seasons/current` | the in-progress season's week, matchups and data-as-of in one payload for Home |

All additions are optional fields or new routes, so the generated client changes additively and the
drift check stays meaningful.

## 4. BFF module changes

```
src/ff_dashboard/analytics/
├── platform.py          NEW  season provenance, capability resolution, platform eras, labels
├── scoring.py           CHG  delegate to upstream source-neutral expressions
├── current_season.py    NEW  in-progress season snapshot (week, live standings, matchups, as-of)
├── brackets.py          NEW  official brackets → shared bracket shape; legacy fallback via bracket.py
├── faab_market.py       NEW  winning + failed bids, bid wars, normalized spend
├── picks.py             NEW  traded-picks ledger
├── player_status.py     CHG  merge nflverse injury reports (≤2024) with Sleeper snapshots
├── aggregation.py       NEW  era-aware helpers: capability-filtered season sets, per-season
│                             normalization (z-score, % of budget), exclusion notes
└── owners.py, records.py, rivalries.py, power.py, insights.py, efficiency.py, draft.py,
    transactions.py, league_history.py, coverage.py     CHG  adopt aggregation.py where they span seasons
```

`aggregation.py` gives every cross-season metric the same three tools:

- `seasons_with(session, capability)` → the season set a metric may legitimately use
- `normalize_within_season(rows, field)` → z-scores / per-game rates when raw values aren't comparable
- `AggregationNote` → `{used_seasons, excluded_seasons, reason}` attached to the response

## 5. Cross-era aggregation rules

| Metric family | Rule | Why |
|---------------|------|-----|
| W-L-T, titles, Sackos, playoff appearances | Sum across all eras directly | Identical semantics |
| Points for/against, records book (highest score, blowouts) | Sum/compare directly, show a rules-era marker on rows where scoring rules differ | Scoring rule changes already exist inside the NFL.com era; platform change adds one more rules era |
| Per-player league points | Always `authoritative_week_points` (official → reconstructed fallback) | Same definition both eras |
| Efficiency / potential points | Computed for every season by the BFF; Sleeper's official `ppts` shown as a cross-check, never mixed into the computed series | One method across eras |
| Transaction "activity" | Counted from moves (add/drop/waiver/trade) only; lineup changes **excluded from cross-era totals**; failed claims (`status='failed'`) and player-less pick/FAAB legs are not moves | Sleeper has no lineup-change log; upstream keeps every row (`00` §4) |
| FAAB spend | Show raw dollars per season; cross-era comparisons use **% of that season's budget** | Budgets may differ by platform |
| Failed bids / bid wars | Sleeper-era only; career views state "since 2026" | Not recorded before |
| Draft (ADP, value, reach) | Unchanged; draft type (snake/auction) carried as a label | Same inputs |
| Divisions | Official when present (Sleeper), BFF-derived for 2010–2019, none otherwise | Existing historical-division logic stays |
| Brackets / placements | Official (Sleeper) or derived (`is_consolation`), with a provenance flag | Existing classifier stays for legacy |
| Injury/status | nflverse weekly reports 2010–2025 (+2026 at go-live) for per-week game status; Sleeper weekly post-games snapshots from 2026 (`player_status_asof`, 7-day cutoff) | Source availability (corrected: 2025 *is* covered) |

## 6. Frontend changes

- `app/shell/SeasonContext.tsx` carries `platform`, `platform_label` and `capabilities` for the
  selected season, so components ask `caps.lineup_change_log.state` instead of fetching twice.
- New design-system primitives (token-driven, no brand colours): `EraMarker`, `CapabilityGate`
  (renders children when available, else a `DataGap` with the capability's reason),
  `ProvenanceNote` (one-line "official / computed / derived" footnote), `BracketView` extension for
  placements.
- Pages touched: Home (current-season command center), Timeline (platform era change), Standings
  (official divisions, potential points), Playoffs (official brackets with placements), Matchups +
  Box score (Sleeper weeks; commissioner override flag; official points source), Team
  (FAAB market, picks, co-owners), Managers (platform accounts; careers with aggregation notes),
  Records (rules-era markers), Players (status timeline), About (platform eras + capability matrix).
- New views: **FAAB market** (inside Team and a league-level tab on Stats), **Pick ledger** (Draft
  page tab), **Player status** (Player detail section).
- A lint rule (`no-restricted-syntax` / grep in CI) blocks comparisons against platform string
  literals outside `lib/platform.ts` label helpers.

## 7. Current-season behavior

The dashboard has so far been a history tool where the newest season was complete. With an
in-progress Sleeper season:

- `is_scored` remains the gate for per-player fantasy points; it becomes `true` for 2026 after S6.
- Week-level freshness: the BFF exposes `finalized` per week (from `matchups.extra_data`) so a
  still-correcting week reads "provisional" — never as final.
- Data-as-of (`DataAsOf.tsx`) already keys on `pipeline_runs`; it now also shows the current NFL
  week. Not real-time: refresh follows the upstream schedule.
- Records book and career totals include in-progress seasons only for completed weeks, labelled.
- **User rule (2026-11-09):** while a season is active, every representation shows its *current*
  state, marked as subject to change; at season end it is static. A game in progress is never a
  result (no tie, no live-score win). Idle postseason team-weeks (no opponent) are not games.

## 8. Testing

- **Mixed-era fixture DB** (foundation): extend the fixture builder with one NFL.com season and one
  Sleeper season sharing owners, including a co-owner, a commissioner override, a failed bid, a
  pick trade, official brackets, a blank team name, and a capability gap on each side.
- **Legacy parity golden tests:** snapshot every existing endpoint's JSON for the legacy fixture
  seasons before D1; assert equality (ignoring the new additive fields) after every milestone.
- **Capability contract tests:** each capability state renders the right affordance; no endpoint
  returns `0` where a capability is `not_on_platform`.
- **Unit tests** for each new analytics module and for every `aggregation.py` rule in §5.
- **Visual regression:** one baseline per era for Standings, Box score, Playoffs, Manager profile —
  the two eras must look like the same product.
- **Guard checks:** the existing forbidden-write grep; a new grep that `web/src` has no platform
  string comparisons outside `lib/platform.ts`.
