# 05 — API Contract (the analytics BFF)

The frontend consumes Phase 2 through this HTTP API and **nothing else**. Like Phase 1, the
contract is canonical: the BFF must implement these; the frontend must not depend on anything
outside this list. The frontend's TypeScript types are generated from this API's OpenAPI
document, so the contract is enforced at build time.

## Conventions (inherited from Phase 1, kept identical)

- Base URL: `http://127.0.0.1:8800` (configurable via `DASHBOARD_HOST` / `DASHBOARD_PORT`).
- All endpoints are **GET** (read-only).
- Every success response is an envelope: `{"data": ..., "meta": {...}}`.
- `meta` carries `last_updated` (ISO timestamp of underlying data), `source`,
  `pipeline_run_id` — sourced from Phase 1's latest pipeline run.
- Errors: `{"error": "...", "detail": "...", "status": 4xx}` (same shape as Phase 1).
- Pagination: offset/limit, default 50, max 500.
- Versioned under `/v1`. OpenAPI at `/openapi.json`, docs at `/docs`.
- **Data-gap marker:** where a metric is unavailable for the requested scope, the endpoint
  returns `200` with `data` containing an explicit `{"available": false, "reason": "..."}`
  object (or per-row `available` flags) rather than zeros or a 404. This is how the
  "honest about gaps" requirement (N2.2) is enforced at the contract level.

> Phase 2 endpoints are **additive** to Phase 1's. Where a view needs only a plain Phase 1
> fact (e.g. raw player metadata), the BFF may re-expose it under `/v1` for a single frontend
> surface, but it computes nothing new for those — it reuses the repository read.

## Endpoints

### Health / meta

| Endpoint | Description |
|----------|-------------|
| `GET /health` | `{"status":"ok"}` liveness |
| `GET /v1/meta` | Data freshness: latest pipeline run, per-source health, coverage summary (which seasons are scored, whether reconstruction is complete) — powers the "data as of" indicator and gap banners |

### Home / command center

> **No `/v1/home` composite endpoint.** The landing view is composed **client-side** from the
> standings, records, top-scorers, and season/championship endpoints below (the SPA does
> orchestration, not math). This
> replaced the originally-planned single composite; see `04_ANALYTICS_MODEL.md` §"League
> command center" and `07_PAGES_AND_VIEWS.md`.

### Seasons & standings

| Endpoint | Description |
|----------|-------------|
| `GET /v1/seasons` | All seasons with status, champion, scored/availability coverage flags |
| `GET /v1/seasons/{season_id}` | Season summary: champion, runner-up, last place, week counts |
| `GET /v1/seasons/{season_id}/standings?through_week={n}` | Standings (current or as-of week n), with streaks; carries `rank_basis` + `tiebreak_caveat` |
| `GET /v1/seasons/{season_id}/standings/insights?through_week={n}` | Schedule-luck insight: all-play win pct, expected wins, luck delta, PF rank |
| `GET /v1/seasons/{season_id}/standings/timeline` | Rank (and points-for) per team per week — for the standings-over-time chart |
| `GET /v1/seasons/{season_id}/power?through_week={n}` | Power ranking + components + weights per team, including all-play win pct |
| `GET /v1/seasons/{season_id}/power/timeline` | Power score per team per week |

> **Not yet implemented:** `GET /v1/seasons/{season_id}/bracket` (playoff/post-season results).
> The route and a Playoffs/Bracket page were specified (F2.3) but not built; the
> "post-regular-season, bracket-not-proven" caveat still applies if/when added. Tracked in
> `10_OPEN_QUESTIONS.md`.

### Matchups & box scores

| Endpoint | Description |
|----------|-------------|
| `GET /v1/seasons/{season_id}/weeks/{week}/matchups` | All matchups for a week with scores + win/loss. Each game card carries `is_close` / `is_blowout` (backend margin flags) and each side a `entering_record` `{wins,losses,ties}` (regular-season record before that week) |
| `GET /v1/matchups/{matchup_id}/box-score` | Both lineups, per-player points + breakdown (DST included), bench points, optimal-lineup + points-left-on-bench, projection-vs-actual, team point share, lineup-value labels; a genuinely-missing DEF row flagged |

### Teams

| Endpoint | Description |
|----------|-------------|
| `GET /v1/teams/{team_id}` | Team season summary (record, rank, owner) |
| `GET /v1/teams/{team_id}/roster?week={n}` | Roster snapshot for a week |
| `GET /v1/teams/{team_id}/schedule` | Week-by-week results for the team's season |
| `GET /v1/teams/{team_id}/scoring-trend` | Points per week vs league average — for the chart |
| `GET /v1/teams/{team_id}/transactions` | Exact recorded transaction log involving the team that season, including dates, type, direction, waiver priority, nullable FAAB, notes, and slot-change `extra_data` |
| `GET /v1/teams/{team_id}/roster-moves` | Derived roster-diff fallback: add/drop/retain from week-over-week roster diffs (`available:false` when <2 snapshots) |

### Owners / managers

| Endpoint | Description |
|----------|-------------|
| `GET /v1/owners` | All managers with quick career line (record, championships) |
| `GET /v1/owners/{owner_id}` | Career aggregate + trophy case + consistency insight |
| `GET /v1/owners/{owner_id}/seasons` | Season-by-season record table. Each row carries a derived `result` (`"Champion"`/`"Runner-up"`/`"3rd place"`/`"Nth"`, `null` when rank-less) and a data-derived `made_playoffs` (`true`/`false`/`null`) |
| `GET /v1/owners/{owner_id}/trajectory` | Finish/points per season — for the chart |
| `GET /v1/owners/{owner_id}/head-to-head/{other_owner_id}` | All-time pairwise record + superlatives |
| `GET /v1/owners/rivalry-matrix` | Full N×N win-pct matrix — for the heatmap |

### Records book

| Endpoint | Description |
|----------|-------------|
| `GET /v1/records` | The full records book: each superlative with value + deep-link context |
| `GET /v1/records/championships` | Championship history / dynasty timeline |

### Draft

| Endpoint | Description |
|----------|-------------|
| `GET /v1/seasons/{season_id}/draft` | Draft board, round-by-round, by team |
| `GET /v1/seasons/{season_id}/draft/value` | Pick-value analysis (steals/busts) for the season |
| `GET /v1/records/draft` | Best/worst draft picks ever |

### Players

| Endpoint | Description |
|----------|-------------|
| `GET /v1/players?name=&position=&nfl_team=&active=&limit=&offset=` | Searchable league-relevant index (ever-rostered players only; no public `scope=all` or `has_scored` field) |
| `GET /v1/players/{player_id}` | Metadata + cross-platform IDs |
| `GET /v1/players/{player_id}/insights` | Best week/best season/league roster-span/most-rostered-by summary |
| `GET /v1/players/{player_id}/scoring?season={y}` | Weekly scoring history (raw + league points) for the chart |
| `GET /v1/players/{player_id}/ownership` | Ownership timeline within the league |
| `GET /v1/players/{player_id}/availability?season={y}` | Per-week availability (current season; gap-marked otherwise) |
| `GET /v1/stats/top-scorers?season={y}&week={w}&position={p}&limit={n}` | Top scorers |
| `GET /v1/stats/season-totals?season={y}&position={p}` | Season totals by position |

### Global search

| Endpoint | Description |
|----------|-------------|
| `GET /v1/search?q={query}` | Typeahead across owners, teams, players, seasons; returns typed hits with deep-link targets |

Hit shape is unchanged: `{type, id, label, sublabel, href}` (`SearchHit`). Match classes:

- **owner** → `/managers/{owner_id}` — display-name match.
- **team** → `/managers/{owner_id}` — a **fantasy team name** match. There is no
  standalone team page, so a team hit deep-links to the owner who held that name;
  a name reused across seasons collapses to its most-recent owner (one hit).
- **season** → `/standings` — year-text match (season context switches client-side).
- **player** → `/players/{player_id}` — **league-relevant only** (ever rostered); a
  never-rostered nflverse "ghost" never appears. Surfaced two ways: by name, and by
  **NFL-team token** — a city / nickname / abbreviation (e.g. `Vikings` / `Minnesota`
  / `MIN`, multi-team metros like `New York` → both franchises) expands into that
  team's players. The NFL team itself gets no standalone hit.

Hardening: SQL LIKE wildcards (`%` `_`), regex metacharacters, and `<script>`/SQL
injection strings are treated as inert literal data — re-filtered casefold (no
`re`) over parameterized reads, so they neither over-match nor inject.

## Sample responses

### `GET /v1/owners/{owner_id}/head-to-head/{other_owner_id}`

```json
{
  "data": {
    "owner_a": { "owner_id": 3, "display_name": "Maverick" },
    "owner_b": { "owner_id": 7, "display_name": "Iceman" },
    "games_played": 22,
    "a_wins": 12, "b_wins": 9, "ties": 1,
    "a_win_pct": 0.545,
    "avg_margin_for_a": 4.8,
    "cumulative_margin_for_a": 105.6,
    "highest_scoring_meeting": {
      "season_year": 2021, "week": 9, "matchup_id": 612,
      "a_score": 141.2, "b_score": 138.7
    },
    "most_lopsided_meeting": {
      "season_year": 2019, "week": 3, "matchup_id": 408,
      "margin_for_a": 64.1
    },
    "closest_meeting": {
      "season_year": 2022, "week": 11, "matchup_id": 701,
      "margin_for_a": 0.4
    },
    "playoff_meetings": 3,
    "available": true
  },
  "meta": { "last_updated": "2025-11-19T08:00:14Z", "source": "reconstruct", "pipeline_run_id": 142 }
}
```

### `GET /v1/matchups/{matchup_id}/box-score` (gap-aware excerpt)

DST is scored end-to-end, so a DEF starter returns real `league_points` and a
defense `breakdown` like any other slot. A DEF starter whose scored row is
genuinely missing for that team/week still returns `"league_points": null,
"available": false, "reason": "team_defense_not_scored"` — never a fake 0.

```json
{
  "data": {
    "matchup_id": 712, "season_year": 2024, "week": 5, "is_playoff": false,
    "home": {
      "team_id": 47, "team_name": "The Couch GMs", "owner_name": "Maverick",
      "total_score": 124.82,
      "bench_points": 38.4,
      "optimal_total": 131.1,
      "points_left_on_bench": 6.28,
      "lineup": [
        {
          "roster_slot": "QB", "player_id": 882, "player_name": "Lamar Jackson",
          "league_points": 27.78, "is_starter": true,
          "breakdown": { "passing": 19.48, "rushing": 8.30, "bonus": 0.0 },
          "projection": 22.4, "available": true
        },
        {
          "roster_slot": "DEF", "player_id": 9001, "player_name": "Ravens D/ST",
          "league_points": 9.0, "is_starter": true,
          "breakdown": { "sacks": 3.0, "interceptions": 2.0, "points_allowed": 4.0 },
          "projection": null, "available": true
        }
      ]
    },
    "away": { "...": "same shape" },
    "winner_team_id": 47
  },
  "meta": { "...": "..." }
}
```

### `GET /v1/meta` (coverage powering gap banners)

```json
{
  "data": {
    "latest_run": { "run_id": 142, "status": "success", "finished_at": "2025-11-19T08:00:14Z" },
    "coverage": {
      "seasons_present": [2010, 2011, "...", 2025],
      "seasons_scored": [2016, "...", 2025],
      "reconstruction_complete": true,
      "availability_current_season_only": true,
      "dst_scoring_complete": true
    }
  },
  "meta": { "...": "..." }
}
```

## Error format (identical to Phase 1)

```json
{ "error": "service_unavailable", "detail": "No successful pipeline run yet", "status": 503 }
```

Common: `400 bad_request`, `404 not_found`, `503 service_unavailable` (pipeline never ran).

## What's NOT in this API

- No write endpoints. No pipeline control. No predictions/recommendations (Phase 3).
- No authentication (binds to localhost). No third-party calls.

## Versioning

First published version is `v1`. Breaking changes mount a `/v2` prefix alongside `/v1`. The
frontend client is regenerated from `/openapi.json` whenever the contract changes.
