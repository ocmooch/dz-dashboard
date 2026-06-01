# P0 — Data-readiness note

**Date:** 2026-05-29
**DB:** `~/danger-zone/data/fantasy.db` (282 MB), read read-only by the dashboard.
**Latest pipeline run:** `run_id=56`, status `success`.

## Verdict: READY. Reconstruction is complete; all of P1–P11 may proceed.

Probed directly against the live database:

| Check | Result | Matches `03_DATA_ACCESS.md`? |
|-------|--------|------------------------------|
| Seasons present | 2010–2025 (all 16) | ✅ |
| Scored seasons (`player_stats_scored`) | **2016–2025** (182,037 rows) | ✅ 2010–2015 unscored, as documented |
| Champions set | every completed season has `champion_team_id` | ✅ |
| Matchups span all weeks | 16–17 weeks per season (not just week 1) | ✅ |
| All 18 tables present | leagues … source_health | ✅ |

## Known gaps (surfaced honestly, never faked — see `03_DATA_ACCESS.md`)

- **2010–2015 unscored:** matchup/team scores exist from reconstruction, but no
  player-level league scoring. Box-score breakdowns for these seasons render a
  `DataGap`, not zeros.
- **Availability is current-season-only:** historical free-agent/waiver
  availability is not reconstructable.
- **DST/team-defense scoring incomplete:** DST starter slots are flagged
  "not scored (known gap)".

These are reported by `GET /v1/meta` (`coverage.seasons_scored`,
`availability_current_season_only`, `dst_scoring_complete`) so the frontend can
drive gap affordances from the contract.
