# Handoff → Player Identity Resolution (stamp out `player_id` confusion permanently)

**Read `00-data-integrity-program.md` first.** · **Status (2026-06-16):** ◐ split by repo — Part B2
(dashboard detection) ☑ shipped on `feature/data-coverage-matrix-dashboard`; Part A (danger-zone
crosswalk + identity-aware ingest) ◐ early BUILD on `feature/player-identity-crosswalk` (table NOT
yet on the live DB, not seeded, ingest not identity-aware = Units B+C); Part B1 (dashboard consume
canonical = Unit D) ⊘ blocked on Part A. Live tracker: `docs/ACTIVE_WORK.md` §0. · **Repos:**
canonical fix in
`../danger-zone` (Phase 1); consume/detect in `dz-dashboard` (Phase 2). · **Extends:** F-25
(`docs/ACTIVE_WORK.md` §2) + `docs/handoffs/players-audit-danger-zone.md` (D1–D5). · **Authored:**
2026-06-16 against the live DB.

This handoff is the *next layer* beyond the existing players-audit handoff. That one covered NULL
metadata (D1/D2), `is_active` semantics (D3), ghost players (D4), and duplicate roster rows (D5).
**It did not cover the cross-source identity split** — the most damaging case, because it strands
real data under a record the roster never points at. That is this handoff's job.

---

## The problem, precisely

The same real player can exist as **two `player_id` rows from two ingestion sources** that were
never reconciled:

- an **NFL.com identity** (carries `nfl_com_player_id`, used by league rosters / transactions /
  the box-score points and status), and
- an **nflverse identity** (carries `gsis_id`, used by scored stats and injury reports).

When ingestion fails to recognize they're the same person, it mints a second stub. The league side
(rosters) attaches to one; the stats/injury side attaches to the other. The dashboard, reading
read-only and doing no math, renders whichever the roster points at — so the player shows as a
no-data DNP while their real production and injury history sit invisible under the twin.

This is distinct from the existing findings:
- **≠ D5** (duplicate *roster rows* — same player on two teams in one week; resolved).
- **≠ D4** (ghost players never rostered *and* never scored). Here the twin *is* scored/injured —
  it's not a ghost, it's a misfiled real record.
- It is the unhandled half of **D4's relevance filter**: filtering to "rostered player_ids" would
  *hide* the stats-bearing twin. Relevance must be applied to *resolved clusters*, never raw ids.

### Canonical reproduction (verify before and after)

```sql
-- Two "Mike Williams / WR / LAC" rows = one real person (2017 Chargers rookie), split by source:
SELECT player_id, name_full, position, nfl_team, rookie_year,
       first_rostered_season, last_rostered_season, gsis_id, nfl_com_player_id
FROM players WHERE player_id IN (1032, 25239);
-- 1032: nfl_com_player_id=2558846, gsis_id NULL, first_rostered_season=2017 (the ROSTER side)
-- 25239: gsis_id=00-0033536, nfl_com_player_id NULL, rookie_year=2017 (the STATS/INJURY side)

SELECT player_id, COUNT(*) FROM team_rosters WHERE season_year=2017
  AND player_id IN (1032,25239) GROUP BY player_id;          -- only 1032 rostered (5 wks)
SELECT player_id, week, total_points FROM player_stats_scored ps
  JOIN seasons s ON s.season_id=ps.season_id
  WHERE s.year=2017 AND player_id IN (1032,25239);           -- only 25239 has stats (W7=0.0 …)
SELECT player_id, week, report_status, report_primary_injury FROM player_injury_reports
  WHERE season_year=2017 AND player_id IN (1032,25239);      -- only 25239 has injuries (Out/Back)
```

### Footprint (live DB, 2026-06-16 — reproduce, don't trust)

- 4,286 player rows; **1,247 ever rostered**.
- **184 duplicate `name_full` groups (373 rows)**; **18 of those groups include a rostered
  player** → the league-relevant split-risk set to triage first.
- **1,403 players have scored stats but were never rostered** — this set contains both genuine
  legacy-era non-league players (workstream 2's relevance filter handles those) *and* the
  stranded stats-twins (this handoff merges those). Distinguishing the two is the core triage.

```sql
-- League-relevant duplicate-name groups (triage set): a same-name group with ≥1 rostered member.
WITH dup AS (SELECT name_full FROM players GROUP BY name_full HAVING COUNT(*)>1)
SELECT p.name_full, p.player_id, p.gsis_id, p.nfl_com_player_id,
       p.first_rostered_season, p.last_rostered_season,
       EXISTS(SELECT 1 FROM team_rosters r WHERE r.player_id=p.player_id) AS rostered,
       EXISTS(SELECT 1 FROM player_stats_scored s WHERE s.player_id=p.player_id) AS scored,
       EXISTS(SELECT 1 FROM player_injury_reports i WHERE i.player_id=p.player_id) AS injured
FROM players p JOIN dup ON dup.name_full=p.name_full
WHERE p.name_full IN (SELECT name_full FROM players p2
                      JOIN team_rosters r2 ON r2.player_id=p2.player_id GROUP BY name_full)
ORDER BY p.name_full, rostered DESC;
```

The signature of a stranded split: within one name group, a **rostered row with no scored/injury
data** beside a **non-rostered row that has them**, with complementary external IDs (one
`nfl_com_player_id`, one `gsis_id`).

---

## Part A — Canonical fix (danger-zone / ff-pipeline) — the durable answer

> Read-only boundary: this part is **not** a dashboard PR. It is the only place the merge can
> happen. Mirror the commissioner/owner-identity migration pattern (`owner_identities.py` already
> exists in `repository/`) — a link table + loader + `queries.*` helper, not destructive surgery.

1. **Build a player-identity crosswalk (link table), don't hard-delete.** Add a
   `player_identity` (or extend `owner_identities`-style) mapping: `member_player_id → canonical_player_id`.
   Choose the canonical id deterministically (prefer the rostered/NFL.com side, since rosters and
   the box-score join key already point there; alias the nflverse side to it). Keeping a link table
   (vs. repointing every FK and dropping rows) is reversible, auditable, and survives re-ingest.
   - **Crosswalk fuel already in the DB:** the `players` table carries `gsis_id`,
     `nfl_com_player_id`, `espn_id`, `sleeper_id`, `yahoo_id`. nflverse publishes a
     gsis↔nfl_com↔espn↔… id map. Match members on any shared external id first (high confidence);
     fall back to `name_full` + overlapping era + position for the residual, flagged for human
     confirmation. Do **not** auto-merge on name alone.
2. **Make ingestion identity-aware (the permanent part).** Before `_create_stub_players` mints a
   new row, resolve against the crosswalk / external-id map so an nflverse stat row attaches to the
   existing NFL.com player (and vice-versa) instead of creating a twin. This is what stops the
   problem recurring on every future crawl — without it, A only fixes today's DB.
3. **Expose the canonical identity read-only** in `queries.py`: a helper returning, for any
   member id, its `canonical_player_id` and the full member set — so the dashboard can union
   stats/injuries across the cluster through one repository call (no dashboard-side joins).
4. **Idempotency + re-ingest test:** re-running the relevant crawl must not recreate twins and must
   keep the crosswalk stable.

**Done when:** every league-relevant stranded split (start from the 18-group triage set) resolves
to one canonical identity whose roster, scored stats, and injuries reconcile; a fresh crawl does
not mint new twins; the crosswalk + canonical-lookup helper are queryable read-only.

## Part B — Dashboard (dz-dashboard) — consume + detect (no identity math of its own)

The dashboard must not invent reconciliation logic that disagrees with Phase 1 — that would
re-create the very "frontend can't disagree with backend" boundary the project forbids in reverse.
Two honest roles:

1. **Consume the canonical identity once Part A lands.** Where `analytics/matchups.py`,
   `analytics/players.py`, and `analytics/injuries.py` join on `player_id`, route through the new
   `queries.py` canonical helper so a box score unions the cluster's stats/injuries. This is the
   step that makes Mike Williams render his real 0.0 + "Out (Back)" instead of a no-data DNP.
   Gate it on Part A being present (helper returns identity-as-itself when no crosswalk exists, so
   the dashboard degrades gracefully).
2. **Until Part A lands — detect and report, don't paper over.** Add a read-only *detection* pass
   (feeds workstream 2's matrix) that flags league-rostered players whose own record has no
   scored/injury data while a same-name external-id-complementary twin does. Surface it as a
   data-quality signal (the project already favors neutral, removable "needs attention" cues — see
   memory `feedback-be-skeptical-of-own-flags`), **not** as a silent on-the-fly union. The union is
   Part A's job; the dashboard's interim job is to make the split *visible and countable* so it
   can be driven to zero upstream.

**Done when (dashboard):** with Part A present, the canonical reproduction (matchup 1823, Mike
Williams) renders unioned stats + injury context; with Part A absent, the detection pass counts the
splits and the matrix reports them; `gen:api` drift check clean; no metric/identity math added to
`web/`.

## Suggested order
A1 (crosswalk) → A2 (identity-aware ingest) → A3 (read-only helper) → B1 (dashboard consume) in
one coordinated cycle; B2 (detection) can ship immediately, independent of A, as the interim signal
and the verification that A drove the count to zero.

## Update on completion
F-25 status in `docs/ACTIVE_WORK.md` §2; the prior `players-audit-danger-zone.md` cross-reference;
memory `player-stub-duplicates` (note the cross-source-split dimension and the crosswalk fix).
