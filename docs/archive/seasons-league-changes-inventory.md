# /seasons/ — League-changes inventory & display framework

**Purpose.** Decide, per kind of NFL.com "league change," whether and how it appears in
each season's section of `/seasons/`. This doc enumerates **every** `setting_change` in the
league's history so nothing is glossed over, groups like-kind entries for per-type decisions,
and records the display + rephrasing rules to implement.

**Source.** `transactions` rows with `transaction_type = 'setting_change'`; the human text is
`extra_data.description`. Extraction today lives in `analytics/league_history.py`
(`_setting_changes`, `_SETTING_PATTERNS`, `_resolve_setting_gaps`). Today only 6 regexes are
surfaced; ~88% of entries are silently dropped. This inventory replaces that allowlist with an
explicit, auditable per-type decision.

**Counts.** 267 total entries · 16 seasons (2010–2025) · 58 in-season / 209 off-season ·
34 canonical types.

## Off-season vs in-season

Each entry is classified by comparing its `executed_at` date to that NFL season's **Week-1
kickoff** (table in the generator). `off` = league setup before kickoff; `IN` = a change made
once games were being played (rarer, higher stakes for competitive integrity). This split is
**automated** and will drive a visual distinction (e.g. an "in-season" marker), independent of
the 3 display tiers below.

## Display model (3 tiers)

- **T1 — Major / highlighted.** Top-level, headlined. Game-defining rule changes.
- **T2 — Significant.** Always displayed, but not headlined.
- **T3 — Minor / routine.** Always collapsed under one broad label per season
  (e.g. "12 routine admin/draft-logistics changes"), expandable on click to show every entry.

All entries are represented — nothing is dropped. T3 is collapsed-by-default, not omitted.
In-season T1/T2 entries get the in-season marker and should never be down-tiered for timing.

## Audience rephrasing (automated)

Raw NFL.com strings read like a system log. Each **kept** type gets a human label + a sentence
templated from the captured `before`/`after`. Examples:

- `changed Draft Type from 'offline' to 'live'` → **Draft format** — "Moved to a live online draft (was offline)."
- `changed Trade Review Type … to 'No Review'` → **Trade approval** — "Trades now process automatically (was league vote)."
- `changed Fee for Joining League from '100.00' to '125.00'` → **Entry fee** — "Buy-in raised to $125 (was $100)."
- `updated playoff teams` (headline-only) → **Playoff field** — source-limited fallback naming the actor.

---

## Combined list — like-kind types (decide each here)

`n` = total occurrences · `in-szn` = how many happened in-season · suggested category/tier/label
are **starting points to override**. Fill the **Your call** column. Ordered by first appearance.

| Canonical type | n | in-szn | years | Suggested category | Sugg. tier | Suggested label | Your call | Notes |
|---|--:|--:|---|---|:--:|---|:--:|---|
| updated scoring settings | 7 | 1 | 2010–2024 | Scoring rules | T1 | Scoring settings | **SPLIT** | T1 derived 2010→2011 diff; T3 hedged 2011–2024 (#1) |
| Draft Time | 23 | 0 | 2010–2025 | Draft logistics | T3 | Draft scheduling | **T3** | (#15) |
| Draft Order | 12 | 0 | 2010–2023 | Draft logistics | T3 | Draft order | **T3** | annual default-reset (#16) |
| Fee for Joining League | 5 | 0 | 2010–2013 | Money | T1 | Entry fee | **T2** | buy-in timeline; note: last NFL.com-recorded change (#10) |
| Trade Reject Time | 1 | 1 | 2010 | Trade rules | T2 | Trade reject window | **T2** | (#9) |
| Trade Review Type | 5 | 3 | 2010–2025 | Trade rules | T1 | Trade approval | **SPLIT** | T2 2010/2011 transitions; T3 2023–25 re-confirms (#7) |
| Post Draft Players | 1 | 1 | 2010 | Transaction rules | T2 | Post-draft players | **T2** | originating standard, never changed (#12) |
| Undroppable List | 1 | 1 | 2010 | Transaction rules | T2 | Undroppable list | **T2** | originating standard, never changed (#13) |
| Playoff Settings | 4 | 4 | 2010–2011 | Playoff format | T1 | Playoff format | **T1** | before/after carries weeks + field size (#3) |
| updated playoff teams | 16 | 16 | 2010–2017 | Playoff format | T1 | Playoff field | **T2** | missing context; field size not derivable (#4) |
| updated roster positions | 8 | 0 | 2011–2021 | Roster slots | T1 | Roster positions | **T1** | fully resolved: starting + reserve/IR diffs (#2) |
| Division (per-manager/team) | 36 | 0 | 2011–2020 | Divisions | T3 | Division assignment | **T3→T1** | collapse each cluster (4) into one T1 realignment event (#22) |
| randomized Custom Draft Order | 3 | 0 | 2011–2020 | Draft logistics | T3 | Draft order | **T3** | (#17) |
| Draft Type | 13 | 0 | 2011–2025 | Draft format | T1 | Draft format | **T3** | annual default-reset, not real; in-person yr(s) deducible? (#14) |
| Player Trades Count (per-manager/team) | 12 | 0 | 2011 | Admin/correction | T3 | Trade-count correction | **T3** | counter reset (#30) |
| Player Adds Count (per-manager/team) | 12 | 0 | 2011 | Admin/correction | T3 | Add-count correction | **T3** | counter reset (#29) |
| Trade Deadline | 3 | 1 | 2011–2019 | Trade rules | T2 | Trade deadline | **SPLIT** | T1 2019 first-ever deadline; T3 2011 net-zero shuffle (#8) |
| Edit Poll Permission (per-manager/team) | 11 | 0 | 2011 | Admin perms | T3 | Permission toggle | **T3** | (#24) |
| Edit Story Permission (per-manager/team) | 32 | 11 | 2011–2013 | Admin perms | T3 | Permission toggle | **T3** | (#23) |
| Waiver Period | 1 | 1 | 2011 | Waiver/FAAB | T2 | Waiver period | **T2** | gameplay impact, not high-importance (#6) |
| Logo Lock (per-manager/team) | 2 | 2 | 2012 | Admin perms | T3 | Logo lock | **T3→T2** | one "punishment" event: sully locked mike (#25) |
| Lineup Changes Lock (per-manager/team) | 2 | 2 | 2012 | Admin perms | T3 | Lineup lock | **T3→T2** | folds into the same #25 punishment event |
| assigned League Management Privileges | 8 | 0 | 2013–2024 | Commissioner | T3 | Commish assigned | **T3→T1** | collapse into handoff-of-power events; xref Commish history (#31) |
| removed League Management Privileges | 5 | 1 | 2014–2022 | Commissioner | T3 | Commish removed | **T3→T1** | folds into #31 handoff events |
| Reset the draft | 4 | 0 | 2014–2025 | Draft logistics | T3 | Draft reset | **T3** | revisit if tied to in-person draft / signif. change (#19) |
| League Schedule for Week N | 13 | 0 | 2014 | Schedule edits | T3 | Weekly schedule edit | **T3→T2** | collapse 13 rows into one T2 "schedule rebuilt" event (#21) |
| Standings Tiebreaker | 2 | 2 | 2014–2018 | Standings | T1 | Tiebreaker | **T2** | tail of legacy best-of-3→PF shift; see note (#11) |
| Time Per Pick | 5 | 0 | 2017–2023 | Draft logistics | T3 | Pick clock | **SPLIT** | T2 era changes (15s→120s); T3 transient experiments (#18) |
| Waiver Priority (per-manager/team) | 12 | 10 | 2017–2018 | Admin | T3 | Waiver priority set | **T3→T2** | one event: 2018 manual reorder (12→3 cascade) (#26) |
| updated the Draft Board | 1 | 0 | 2018 | Draft logistics | T3 | Draft board | **T2+** | missing context; ≥T2, 2018-09-02 w/ a Reset (#20) |
| Waiver Budget | 1 | 0 | 2021 | Waiver/FAAB | T1 | FAAB budget | **T1** | merged w/ Waiver Type → FAAB switch (#5) |
| Waiver Type | 1 | 0 | 2021 | Waiver/FAAB | T1 | Waiver system | **T1** | merged w/ Waiver Budget → FAAB switch (#5) |
| Adjusted Pts For Week N (per-manager/team) | 4 | 0 | 2022 | Scoring correction | T2 | Manual scoring adjustment | **T1** | one event, re-attribute to 2021 Wk17 (#28) |
| Waiver Budget (per-manager/team) | 1 | 1 | 2022 | Admin | T3 | Per-team FAAB set | **T2** | mid-season FAAB bump 39→76; cause not recoverable (#27) |

---

## Full chronological list — every entry (year → date)

`phase`: `IN` = in-season, `off` = pre-kickoff setup. Verbatim source `description`.

| year | date | phase | description |
|---|---|:--:|---|
| 2010 | 2010-07-14 | off | harry updated scoring settings |
| 2010 | 2010-07-18 | off | harry changed Draft Time from 'Aug 29, 2010 7:30pm PDT' to 'Jul 30, 2010 7:30pm PDT' |
| 2010 | 2010-07-21 | off | harry changed Draft Time from 'Jul 30, 2010 7:30pm PDT' to 'Jul 28, 2010 6:30pm PDT' |
| 2010 | 2010-07-22 | off | harry updated scoring settings |
| 2010 | 2010-07-22 | off | harry updated scoring settings |
| 2010 | 2010-07-25 | off | harry changed Draft Order from 'random' to 'custom' |
| 2010 | 2010-07-26 | off | harry updated scoring settings |
| 2010 | 2010-07-29 | off | harry updated scoring settings |
| 2010 | 2010-08-06 | off | harry changed Fee for Joining League from '0.00' to '20.00' |
| 2010 | 2010-09-20 | IN | harry changed Trade Reject Time from '2 days' to '1 day' |
| 2010 | 2010-10-02 | IN | harry changed Trade Review Type from 'League Votes (by team owners)' to 'League Manager Veto' |
| 2010 | 2010-10-15 | IN | harry changed Post Draft Players from 'Follow Waiver Rules' to 'Free Agents' |
| 2010 | 2010-11-02 | IN | harry changed Undroppable List from 'NFL.com Fantasy' to 'None' |
| 2010 | 2010-12-13 | IN | harry changed Playoff Settings from 'Weeks 15, 16 & 17 - 6 teams' to 'Weeks 15 & 16 - 4 teams' |
| 2010 | 2010-12-13 | IN | harry changed Playoff Settings from 'Weeks 15 & 16 - 4 teams' to 'Weeks 15, 16 & 17 - 6 teams' |
| 2010 | 2010-12-14 | IN | harry updated playoff teams |
| 2010 | 2010-12-14 | IN | harry updated playoff teams |
| 2010 | 2010-12-14 | IN | harry updated playoff teams |
| 2010 | 2010-12-14 | IN | harry changed Playoff Settings from 'Weeks 15 & 16 - 4 teams' to 'Weeks 15, 16 & 17 - 6 teams' |
| 2011 | 2011-07-10 | off | harry updated scoring settings |
| 2011 | 2011-07-10 | off | harry changed Trade Review Type from 'League Manager Veto' to 'No Review' |
| 2011 | 2011-07-25 | off | harry updated roster positions |
| 2011 | 2011-08-06 | off | harry changed IAMTHEOMEN's Division from '1' to '2' |
| 2011 | 2011-08-06 | off | harry changed Final Fantasy Football II's Division from '3' to '1' |
| 2011 | 2011-08-06 | off | harry changed whats going on here's Division from '2' to '1' |
| 2011 | 2011-08-06 | off | harry changed Fie's Division from '1' to '2' |
| 2011 | 2011-08-06 | off | harry changed Caserty da Hershey Squirty's Division from '3' to '2' |
| 2011 | 2011-08-06 | off | harry changed fire in the taco bell's Division from '2' to '1' |
| 2011 | 2011-08-06 | off | harry changed Heathcliff's Haiku Warriors's Division from '1' to '2' |
| 2011 | 2011-08-06 | off | harry changed The Silver Spoon Motherf_ckers's Division from '3' to '2' |
| 2011 | 2011-08-06 | off | harry changed Ahwats'Up Sullay's Division from '2' to '1' |
| 2011 | 2011-08-06 | off | harry changed ThisTeamMakesSullyNervous's Division from '1' to '2' |
| 2011 | 2011-08-06 | off | harry changed DOOKS's Division from '3' to '1' |
| 2011 | 2011-08-06 | off | harry changed TBD's Division from '2' to '1' |
| 2011 | 2011-08-14 | off | harry randomized Custom Draft Order |
| 2011 | 2011-08-15 | off | harry changed Draft Time to 'Aug 17, 2011 7:30pm PDT' |
| 2011 | 2011-08-15 | off | harry changed Draft Type from 'offline' to 'live' |
| 2011 | 2011-08-18 | off | harry IAMTHEOMEN Player Trades Count |
| 2011 | 2011-08-18 | off | harry IAMTHEOMEN Player Adds Count |
| 2011 | 2011-08-18 | off | harry The Mammalian Aliens Player Trades Count |
| 2011 | 2011-08-18 | off | harry The Mammalian Aliens Player Adds Count |
| 2011 | 2011-08-18 | off | harry whats going on here Player Trades Count |
| 2011 | 2011-08-18 | off | harry changed whats going on here Player Adds Count from '16' to '0' |
| 2011 | 2011-08-18 | off | harry Fie Player Trades Count |
| 2011 | 2011-08-18 | off | harry changed Fie Player Adds Count from '15' to '0' |
| 2011 | 2011-08-18 | off | harry 6 Deuce Larry H2Ovaries Player Trades Count |
| 2011 | 2011-08-18 | off | harry 6 Deuce Larry H2Ovaries Player Adds Count |
| 2011 | 2011-08-18 | off | harry I just blue myself Player Trades Count |
| 2011 | 2011-08-18 | off | harry I just blue myself Player Adds Count |
| 2011 | 2011-08-18 | off | harry The Renegades of Funk Player Trades Count |
| 2011 | 2011-08-18 | off | harry The Renegades of Funk Player Adds Count |
| 2011 | 2011-08-18 | off | harry I STOLE THE WATCHES sry serts Player Trades Count |
| 2011 | 2011-08-18 | off | harry I STOLE THE WATCHES sry serts Player Adds Count |
| 2011 | 2011-08-18 | off | harry Ahwats'Up Sullay Player Trades Count |
| 2011 | 2011-08-18 | off | harry Ahwats'Up Sullay Player Adds Count |
| 2011 | 2011-08-18 | off | harry Got Bolognese Player Trades Count |
| 2011 | 2011-08-18 | off | harry Got Bolognese Player Adds Count |
| 2011 | 2011-08-18 | off | harry DOOKS Player Trades Count |
| 2011 | 2011-08-18 | off | harry DOOKS Player Adds Count |
| 2011 | 2011-08-18 | off | harry Talkin About Practice Player Trades Count |
| 2011 | 2011-08-18 | off | harry Talkin About Practice Player Adds Count |
| 2011 | 2011-09-01 | off | harry changed Trade Deadline from 'November 18, 2011' to 'November 25, 2011' |
| 2011 | 2011-09-01 | off | harry changed Trade Deadline from 'November 25, 2011' to 'November 18, 2011' |
| 2011 | 2011-09-01 | off | harry changed Ill Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Ill Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Rob Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Rob Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Jeff Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Jeff Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Chris Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Chris Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Gregg Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Gregg Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Adam Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Adam Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Dave Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Dave Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Don Juan Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed Don Juan Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed brian Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed brian Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed mike Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed mike Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed scott Edit Poll Permission from 'No' to 'Yes' |
| 2011 | 2011-09-01 | off | harry changed scott Edit Story Permission from 'No' to 'Yes' |
| 2011 | 2011-09-12 | IN | harry changed Waiver Period from '2 days' to '1 day' |
| 2011 | 2011-11-02 | IN | harry changed Playoff Settings from 'Weeks 15, 16 & 17 - 6 teams' to 'Weeks 14, 15 & 16 - 6 teams' |
| 2011 | 2011-12-06 | IN | harry updated playoff teams |
| 2012 | 2012-06-25 | off | sully changed Fee for Joining League from '20.00' to '100.00' |
| 2012 | 2012-06-29 | off | sully changed Fee for Joining League from '100.00' to '125.00' |
| 2012 | 2012-08-02 | off | sully changed Draft Time to 'Aug 23, 2012 5:00pm PDT' |
| 2012 | 2012-08-02 | off | sully changed Draft Type from 'offline' to 'live' |
| 2012 | 2012-08-14 | off | sully changed Draft Time from 'Aug 23, 2012 5:00pm PDT' to 'Aug 23, 2012 4:00pm PDT' |
| 2012 | 2012-08-16 | off | sully changed Ill Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed Gregg Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed mike Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed Rob Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed Jeff Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed Chris Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed Dave Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed Don Juan Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed scott Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-16 | off | sully changed harry Edit Story Permission from 'No' to 'Yes' |
| 2012 | 2012-08-20 | off | sully changed Draft Time from 'Aug 23, 2012 4:00pm PDT' to 'Aug 23, 2012 5:00pm PDT' |
| 2012 | 2012-09-26 | IN | sully changed SulladisaN1GGER Logo Lock from 'Yes' to 'No' |
| 2012 | 2012-09-26 | IN | sully changed SulladisaN1GGER Logo Lock from 'No' to 'Yes' |
| 2012 | 2012-09-27 | IN | sully changed SulladisaN1GGER Lineup Changes Lock from 'No' to 'Yes' |
| 2012 | 2012-09-28 | IN | sully changed Sulladisa4kingN1GGER Lineup Changes Lock from 'Yes' to 'No' |
| 2012 | 2012-12-04 | IN | sully updated playoff teams |
| 2012 | 2012-12-04 | IN | sully updated playoff teams |
| 2013 | 2013-03-14 | off | sully assigned League Management Privileges to scott. |
| 2013 | 2013-05-28 | off | sully changed Draft Time to 'Aug 24, 2013 4:30pm PDT' |
| 2013 | 2013-05-28 | off | sully changed Draft Type from 'offline' to 'live' |
| 2013 | 2013-05-29 | off | sully randomized Custom Draft Order |
| 2013 | 2013-05-29 | off | sully changed Draft Order from 'snake' to 'custom' |
| 2013 | 2013-05-29 | off | sully changed Fee for Joining League from '125.00' to '150.00' |
| 2013 | 2013-07-25 | off | sully changed Draft Time from 'Aug 24, 2013 4:30pm PDT' to 'Aug 23, 2013 4:00pm PDT' |
| 2013 | 2013-08-02 | off | sully changed I AM CHANGED's Division from '2' to '1' |
| 2013 | 2013-08-02 | off | sully changed IT'S A TRAP's Division from '1' to '2' |
| 2013 | 2013-08-02 | off | sully changed what IS the shawshank rdmption's Division from '1' to '2' |
| 2013 | 2013-08-02 | off | sully changed Papa Fies Back for Seconds's Division from '2' to '1' |
| 2013 | 2013-08-02 | off | sully changed No Sweat Just Chile's Division from '2' to '1' |
| 2013 | 2013-08-02 | off | sully changed HoneyBadgerSwagger's Division from '1' to '2' |
| 2013 | 2013-08-02 | off | sully changed Valar Morghulis's Division from '2' to '1' |
| 2013 | 2013-08-02 | off | sully changed Tainted Basil's Division from '2' to '1' |
| 2013 | 2013-08-02 | off | sully changed MADSKETCH's Division from '1' to '2' |
| 2013 | 2013-08-02 | off | sully changed Sulladismichaelbushleague's Division from '2' to '1' |
| 2013 | 2013-08-02 | off | sully changed reDUMPtion's Division from '1' to '2' |
| 2013 | 2013-08-02 | off | sully changed Anything is Possible's Division from '1' to '2' |
| 2013 | 2013-08-04 | off | sully changed Draft Time from 'Aug 23, 2013 4:00pm PDT' to 'Aug 16, 2013 5:00pm PDT' |
| 2013 | 2013-08-05 | off | sully changed Fee for Joining League from '150.00' to '125.00' |
| 2013 | 2013-08-15 | off | sully changed Draft Time from 'Aug 16, 2013 5:00pm PDT' to 'Aug 16, 2013 8:30pm PDT' |
| 2013 | 2013-08-16 | off | sully changed Draft Time from 'Aug 16, 2013 8:30pm PDT' to 'Aug 16, 2013 8:00pm PDT' |
| 2013 | 2013-09-30 | IN | sully changed Tom Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed Ill Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed Rob Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed Jeff Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed Chris Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed Gregg Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed Dave Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed Dan Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed mike Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed scott Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-09-30 | IN | sully changed harry Edit Story Permission from 'No' to 'Yes' |
| 2013 | 2013-12-03 | IN | sully updated playoff teams |
| 2013 | 2013-12-03 | IN | sully updated playoff teams |
| 2013 | 2013-12-03 | IN | sully updated playoff teams |
| 2014 | 2014-08-04 | off | scott assigned League Management Privileges to Ill. |
| 2014 | 2014-08-04 | off | scott changed Draft Time to 'Aug 23, 2014 10:00am PDT' |
| 2014 | 2014-08-04 | off | scott changed Draft Type from 'offline' to 'live' |
| 2014 | 2014-08-05 | off | scott removed League Management Privileges from brian. |
| 2014 | 2014-08-17 | off | scott changed Draft Order from 'snake' to 'custom' |
| 2014 | 2014-08-23 | off | scott changed Draft Time to 'Aug 23, 2014 11:30am PDT' |
| 2014 | 2014-08-23 | off | scott changed Draft Type from 'offline' to 'live' |
| 2014 | 2014-08-23 | off | scott Reset the draft |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 13 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 12 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 11 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 10 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 9 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 8 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 7 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 6 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 5 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 4 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 3 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 2 |
| 2014 | 2014-09-02 | off | scott changed League Schedule for Week 1 |
| 2014 | 2014-10-09 | IN | scott changed Standings Tiebreaker from 'Head to Head Record' to 'Points For' |
| 2014 | 2014-12-02 | IN | scott updated playoff teams |
| 2014 | 2014-12-02 | IN | scott updated playoff teams |
| 2015 | 2015-08-12 | off | scott changed DEEZ NUTS's Division from '1' to '2' |
| 2015 | 2015-08-12 | off | scott changed THE GRILL's Division from '2' to '1' |
| 2015 | 2015-08-12 | off | scott changed The Iron Bank of Fie Fie's Division from '1' to '2' |
| 2015 | 2015-08-12 | off | scott changed Bed Forbath and Beyond's Division from '1' to '2' |
| 2015 | 2015-08-12 | off | scott changed The Northvale Scumbags's Division from '2' to '1' |
| 2015 | 2015-08-12 | off | scott changed puglISIS's Division from '2' to '1' |
| 2015 | 2015-08-12 | off | scott changed Draft Time to 'Aug 28, 2015 8:00pm PDT' |
| 2015 | 2015-08-12 | off | scott changed Draft Type from 'offline' to 'live' |
| 2015 | 2015-08-17 | off | scott changed Draft Order from 'snake' to 'custom' |
| 2015 | 2015-12-09 | IN | scott updated playoff teams |
| 2015 | 2015-12-09 | IN | scott updated playoff teams |
| 2015 | 2015-12-09 | IN | scott updated playoff teams |
| 2016 | 2016-08-22 | off | scott assigned League Management Privileges to Dave. |
| 2016 | 2016-08-24 | off | Dave changed Draft Time from 'Sep 2, 2016 8:00am PDT' to 'Sep 2, 2016 8:30pm PDT' |
| 2016 | 2016-08-24 | off | Dave changed Draft Order from 'snake' to 'custom' |
| 2016 | 2016-08-24 | off | Dave changed Draft Time to 'Sep 2, 2016 8:00am PDT' |
| 2016 | 2016-08-24 | off | Dave changed Draft Type from 'offline' to 'live' |
| 2016 | 2016-08-24 | off | Dave updated roster positions |
| 2016 | 2016-09-30 | IN | Dave removed League Management Privileges from scott. |
| 2017 | 2017-08-30 | off | Dave changed Draft Order from 'snake' to 'custom' |
| 2017 | 2017-08-30 | off | Dave changed Time Per Pick to '15' |
| 2017 | 2017-09-03 | off | Dave changed CAPPe Diem- Seize the Day Waiver Priority from '5' to '6' |
| 2017 | 2017-09-03 | off | Dave changed Hillary's Cankle Breakers Waiver Priority from '6' to '5' |
| 2017 | 2017-12-05 | IN | Dave updated playoff teams |
| 2017 | 2017-12-05 | IN | Dave updated playoff teams |
| 2018 | 2018-05-13 | off | Jeff removed League Management Privileges from Dave. |
| 2018 | 2018-05-13 | off | Dave assigned League Management Privileges to Jeff. |
| 2018 | 2018-05-18 | off | Jeff assigned League Management Privileges to harry. |
| 2018 | 2018-08-25 | off | Jeff removed League Management Privileges from harry. |
| 2018 | 2018-09-02 | off | Jeff updated the Draft Board |
| 2018 | 2018-09-02 | off | Jeff Reset the draft |
| 2018 | 2018-09-14 | IN | Jeff changed Standings Tiebreaker from 'Head to Head Record' to 'Points For' |
| 2018 | 2018-10-09 | IN | Jeff changed ROBJECTION Waiver Priority from '10' to '11' |
| 2018 | 2018-10-09 | IN | Jeff changed do the SHAWdy lean Waiver Priority from '9' to '10' |
| 2018 | 2018-10-09 | IN | Jeff changed Agents of FIE Waiver Priority from '3' to '4' |
| 2018 | 2018-10-09 | IN | Jeff changed Demaryius Targaryen Waiver Priority from '5' to '6' |
| 2018 | 2018-10-09 | IN | Jeff changed WayneGallman Leviosa Waiver Priority from '6' to '7' |
| 2018 | 2018-10-09 | IN | Jeff changed Now Your Thinking With Bortles Waiver Priority from '7' to '8' |
| 2018 | 2018-10-09 | IN | Jeff changed Doughy Donald's Rushin' Trolls Waiver Priority from '12' to '3' |
| 2018 | 2018-10-09 | IN | Jeff changed Chicken Ks All Day Waiver Priority from '11' to '12' |
| 2018 | 2018-10-09 | IN | Jeff changed Da BearZ and the Melvin Fair Waiver Priority from '8' to '9' |
| 2018 | 2018-10-09 | IN | Jeff changed Chicken Teriyaki Boys Waiver Priority from '4' to '5' |
| 2019 | 2019-09-03 | off | Jeff Reset the draft |
| 2019 | 2019-11-03 | IN | Jeff changed Trade Deadline from 'No Deadline' to 'November 15, 2019' |
| 2020 | 2020-07-04 | off | Jeff assigned League Management Privileges to Chris. |
| 2020 | 2020-08-11 | off | Chris changed Half Bakered's Division from '2' to '1' |
| 2020 | 2020-08-11 | off | Chris changed The Roblet of Fire's Division from '2' to '1' |
| 2020 | 2020-08-11 | off | Chris changed FIEFIEANA JONES's Division from '2' to '1' |
| 2020 | 2020-08-11 | off | Chris changed TopGoff's Division from '2' to '1' |
| 2020 | 2020-08-11 | off | Chris changed The Brigands of Braciole's Division from '2' to '1' |
| 2020 | 2020-08-11 | off | Chris changed Cap'n Cook's Chili P's Division from '2' to '1' |
| 2020 | 2020-08-24 | off | Chris updated roster positions |
| 2020 | 2020-08-24 | off | Chris updated roster positions |
| 2020 | 2020-08-24 | off | Chris changed Time Per Pick from '15' to '300' |
| 2020 | 2020-08-24 | off | Chris changed Draft Time to 'Sep 6, 2020 3:00pm PDT' |
| 2020 | 2020-08-24 | off | Chris changed Draft Type from 'offline' to 'live' |
| 2020 | 2020-08-29 | off | Chris changed Time Per Pick from '300' to '120' |
| 2020 | 2020-08-29 | off | Chris changed Draft Time from 'Sep 6, 2020 3:00pm PDT' to 'Sep 6, 2020 5:30pm PDT' |
| 2020 | 2020-09-02 | off | Chris updated roster positions |
| 2020 | 2020-09-02 | off | Chris randomized Custom Draft Order |
| 2020 | 2020-09-02 | off | Chris changed Draft Order from 'snake' to 'custom' |
| 2020 | 2020-09-04 | off | Chris changed Draft Order from 'snake' to 'custom' |
| 2021 | 2021-08-23 | off | Chris changed Draft Time to 'Aug 29, 2021 4:30pm PDT' |
| 2021 | 2021-08-23 | off | Chris changed Draft Type from 'offline' to 'live' |
| 2021 | 2021-08-27 | off | Chris updated roster positions |
| 2021 | 2021-08-27 | off | Chris updated roster positions |
| 2021 | 2021-08-27 | off | Chris updated roster positions |
| 2021 | 2021-08-27 | off | Chris changed Waiver Budget to '100' |
| 2021 | 2021-08-27 | off | Chris changed Waiver Type from 'Resets to Inverse Standings Order' to 'Waiver Budget' |
| 2021 | 2021-08-27 | off | Chris changed Draft Order from 'snake' to 'custom' |
| 2021 | 2021-08-29 | off | Chris changed Draft Order from 'snake' to 'custom' |
| 2022 | 2022-01-16 | off | Dan changed Smokin Doubs Adjusted Pts For Week 17 from '0.00' to '55.26' |
| 2022 | 2022-01-16 | off | Dan changed CMC Rules Everything Around Me Adjusted Pts For Week 17 from '0.00' to '5.60' |
| 2022 | 2022-01-16 | off | Dan changed Smokin' AJ Adjusted Pts For Week 17 from '0.00' to '28.68' |
| 2022 | 2022-01-16 | off | Dan changed Ice Station Zebra Adjusted Pts For Week 17 from '0.00' to '23.4' |
| 2022 | 2022-08-06 | off | Chris removed League Management Privileges from Jeff. |
| 2022 | 2022-08-06 | off | Chris assigned League Management Privileges to Dan. |
| 2022 | 2022-08-23 | off | Dan changed Draft Time to 'Sep 2, 2022 6:00pm PDT' |
| 2022 | 2022-08-23 | off | Dan changed Draft Type from 'offline' to 'live' |
| 2022 | 2022-08-29 | off | Dan changed Draft Order from 'snake' to 'custom' |
| 2022 | 2022-09-16 | IN | Dan changed Ice Station Zebra Waiver Budget from '39' to '76' |
| 2023 | 2023-07-20 | off | Dan changed Time Per Pick from '120' to '90' |
| 2023 | 2023-07-20 | off | Dan changed Draft Time to 'Sep 2, 2023 4:00pm PDT' |
| 2023 | 2023-07-20 | off | Dan changed Draft Type from 'offline' to 'live' |
| 2023 | 2023-07-29 | off | Dan changed Time Per Pick from '90' to '120' |
| 2023 | 2023-08-20 | off | Dan changed Draft Order from 'snake' to 'custom' |
| 2023 | 2023-11-14 | IN | Dan changed Trade Review Type from 'League Votes (by team managers)' to 'No Review' |
| 2024 | 2024-08-06 | off | Dan assigned League Management Privileges to Rob. |
| 2024 | 2024-08-21 | off | Rob changed Draft Time to 'Sep 2, 2024 12:00pm PDT' |
| 2024 | 2024-08-21 | off | Rob changed Draft Type from 'offline' to 'live' |
| 2024 | 2024-08-29 | off | Rob changed Trade Review Type from 'League Votes (by team managers)' to 'No Review' |
| 2024 | 2024-09-17 | IN | Dan updated scoring settings |
| 2025 | 2025-08-29 | off | Rob changed Draft Time to 'Sep 1, 2025 8:00am PDT' |
| 2025 | 2025-08-29 | off | Rob changed Draft Type from 'offline' to 'live' |
| 2025 | 2025-09-01 | off | Rob Reset the draft |
| 2025 | 2025-09-28 | IN | Rob changed Trade Review Type from 'League Votes (by team managers)' to 'No Review' |

_Generated 2026-06-14 from ../danger-zone/data/fantasy.db (read-only)._

---

## Evidence sheet — verbatim NFL.com phrasings per type

_Grouped by the proposed category. Actor stripped to the front; `×N` = repeats._


### A · Scoring rules

**updated scoring settings** — 7× · 1 in-season · 2010–2024
  - `updated scoring settings` ×6
  - `Dan updated scoring settings`

### B · Roster slots

**updated roster positions** — 8× · 0 in-season · 2011–2021
  - `updated roster positions` ×8

### C · Playoff format

**Playoff Settings** — 4× · 4 in-season · 2010–2011
  - `changed Playoff Settings from 'Weeks 15 & 16 - 4 teams' to 'Weeks 15, 16 & 17 - 6 teams'` ×2
  - `changed Playoff Settings from 'Weeks 15, 16 & 17 - 6 teams' to 'Weeks 15 & 16 - 4 teams'`
  - `changed Playoff Settings from 'Weeks 15, 16 & 17 - 6 teams' to 'Weeks 14, 15 & 16 - 6 teams'`

**updated playoff teams** — 16× · 16 in-season · 2010–2017
  - `updated playoff teams` ×16

### D · Waiver/FAAB system

**Waiver Type** — 1× · 0 in-season · 2021
  - `changed Waiver Type from 'Resets to Inverse Standings Order' to 'Waiver Budget'`

**Waiver Budget** — 1× · 0 in-season · 2021
  - `changed Waiver Budget to '100'`

**Waiver Period** — 1× · 1 in-season · 2011
  - `changed Waiver Period from '2 days' to '1 day'`

### E · Trade rules

**Trade Review Type** — 5× · 3 in-season · 2010–2025
  - `changed Trade Review Type from 'League Votes (by team managers)' to 'No Review'` ×2
  - `changed Trade Review Type from 'League Votes (by team owners)' to 'League Manager Veto'`
  - `changed Trade Review Type from 'League Manager Veto' to 'No Review'`
  - `Dan changed Trade Review Type from 'League Votes (by team managers)' to 'No Review'`

**Trade Deadline** — 3× · 1 in-season · 2011–2019
  - `changed Trade Deadline from 'November 18, 2011' to 'November 25, 2011'`
  - `changed Trade Deadline from 'November 25, 2011' to 'November 18, 2011'`
  - `changed Trade Deadline from 'No Deadline' to 'November 15, 2019'`

**Trade Reject Time** — 1× · 1 in-season · 2010
  - `changed Trade Reject Time from '2 days' to '1 day'`

### F · Money

**Fee for Joining League** — 5× · 0 in-season · 2010–2013
  - `changed Fee for Joining League from '0.00' to '20.00'`
  - `changed Fee for Joining League from '100.00' to '125.00'`
  - `changed Fee for Joining League from '20.00' to '100.00'`
  - `changed Fee for Joining League from '150.00' to '125.00'`
  - `changed Fee for Joining League from '125.00' to '150.00'`

### G · Standings

**Standings Tiebreaker** — 2× · 2 in-season · 2014–2018
  - `changed Standings Tiebreaker from 'Head to Head Record' to 'Points For'` ×2

### H · Transaction rules

**Post Draft Players** — 1× · 1 in-season · 2010
  - `changed Post Draft Players from 'Follow Waiver Rules' to 'Free Agents'`

**Undroppable List** — 1× · 1 in-season · 2010
  - `changed Undroppable List from 'NFL.com Fantasy' to 'None'`

### I · Draft format

**Draft Type** — 13× · 0 in-season · 2011–2025
  - `changed Draft Type from 'offline' to 'live'` ×11
  - `Chris changed Draft Type from 'offline' to 'live'`
  - `Dan changed Draft Type from 'offline' to 'live'`

### J · Draft logistics

**Draft Time** — 23× · 0 in-season · 2010–2025
  - `changed Draft Time from 'Jul 30, 2010 7:30pm PDT' to 'Jul 28, 2010 6:30pm PDT'`
  - `changed Draft Time from 'Aug 29, 2010 7:30pm PDT' to 'Jul 30, 2010 7:30pm PDT'`
  - `changed Draft Time to 'Aug 17, 2011 7:30pm PDT'`
  - `changed Draft Time from 'Aug 23, 2012 4:00pm PDT' to 'Aug 23, 2012 5:00pm PDT'`
  - `changed Draft Time from 'Aug 23, 2012 5:00pm PDT' to 'Aug 23, 2012 4:00pm PDT'`
  - …(+18 more, vary by team/manager)

**Draft Order** — 12× · 0 in-season · 2010–2023
  - `changed Draft Order from 'snake' to 'custom'` ×11
  - `changed Draft Order from 'random' to 'custom'`

**randomized Custom Draft Order** — 3× · 0 in-season · 2011–2020
  - `randomized Custom Draft Order` ×3

**Time Per Pick** — 5× · 0 in-season · 2017–2023
  - `changed Time Per Pick to '15'`
  - `Chris changed Time Per Pick from '300' to '120'`
  - `Chris changed Time Per Pick from '15' to '300'`
  - `changed Time Per Pick from '90' to '120'`
  - `Dan changed Time Per Pick from '120' to '90'`

**Reset the draft** — 4× · 0 in-season · 2014–2025
  - `Reset the draft` ×4

**updated the Draft Board** — 1× · 0 in-season · 2018
  - `updated the Draft Board`

### K · Schedule edits

**League Schedule for Week N** — 13× · 0 in-season · 2014
  - `changed League Schedule for Week 13`
  - `changed League Schedule for Week 12`
  - `changed League Schedule for Week 11`
  - `changed League Schedule for Week 10`
  - `changed League Schedule for Week 9`
  - …(+8 more, vary by team/manager)

### L · Divisions

**Division (per-team)** — 36× · 0 in-season · 2011–2020
  - `changed IAMTHEOMEN's Division from '1' to '2'`
  - `changed Final Fantasy Football II's Division from '3' to '1'`
  - `changed whats going on here's Division from '2' to '1'`
  - `changed Fie's Division from '1' to '2'`
  - `changed Caserty da Hershey Squirty's Division from '3' to '2'`
  - …(+31 more, vary by team/manager)

### M · Admin/permissions

**Edit Story Permission (per-team)** — 32× · 11 in-season · 2011–2013
  - `changed Ill Edit Story Permission from 'No' to 'Yes'` ×3
  - `changed Rob Edit Story Permission from 'No' to 'Yes'` ×3
  - `changed Jeff Edit Story Permission from 'No' to 'Yes'` ×3
  - `changed Chris Edit Story Permission from 'No' to 'Yes'` ×3
  - `changed Gregg Edit Story Permission from 'No' to 'Yes'` ×3
  - …(+9 more, vary by team/manager)

**Edit Poll Permission (per-team)** — 11× · 0 in-season · 2011
  - `changed Ill Edit Poll Permission from 'No' to 'Yes'`
  - `changed Rob Edit Poll Permission from 'No' to 'Yes'`
  - `changed Jeff Edit Poll Permission from 'No' to 'Yes'`
  - `changed Chris Edit Poll Permission from 'No' to 'Yes'`
  - `changed Gregg Edit Poll Permission from 'No' to 'Yes'`
  - …(+6 more, vary by team/manager)

**Logo Lock (per-team)** — 2× · 2 in-season · 2012
  - `changed SulladisaN1GGER Logo Lock from 'Yes' to 'No'`
  - `changed SulladisaN1GGER Logo Lock from 'No' to 'Yes'`

**Lineup Changes Lock (per-team)** — 2× · 2 in-season · 2012
  - `changed Sulladisa4kingN1GGER Lineup Changes Lock from 'Yes' to 'No'`
  - `changed SulladisaN1GGER Lineup Changes Lock from 'No' to 'Yes'`

**Waiver Priority (per-team)** — 12× · 10 in-season · 2017–2018
  - `changed CAPPe Diem- Seize the Day Waiver Priority from '5' to '6'`
  - `changed Hillary's Cankle Breakers Waiver Priority from '6' to '5'`
  - `changed ROBJECTION Waiver Priority from '10' to '11'`
  - `changed do the SHAWdy lean Waiver Priority from '9' to '10'`
  - `changed Agents of FIE Waiver Priority from '3' to '4'`
  - …(+7 more, vary by team/manager)

**Waiver Budget (per-team)** — 1× · 1 in-season · 2022
  - `changed Ice Station Zebra Waiver Budget from '39' to '76'`

### N · Stat corrections

**Adjusted Pts For Week N (per-team)** — 4× · 0 in-season · 2022
  - `changed Smokin Doubs Adjusted Pts For Week 17 from '0.00' to '55.26'`
  - `changed CMC Rules Everything Around Me Adjusted Pts For Week 17 from '0.00' to '5.60'`
  - `changed Smokin' AJ Adjusted Pts For Week 17 from '0.00' to '28.68'`
  - `changed Ice Station Zebra Adjusted Pts For Week 17 from '0.00' to '23.4'`

**Player Adds Count (per-team)** — 12× · 0 in-season · 2011
  - `IAMTHEOMEN Player Adds Count`
  - `The Mammalian Aliens Player Adds Count`
  - `changed whats going on here Player Adds Count from '16' to '0'`
  - `changed Fie Player Adds Count from '15' to '0'`
  - `6 Deuce Larry H2Ovaries Player Adds Count`
  - …(+7 more, vary by team/manager)

**Player Trades Count (per-team)** — 12× · 0 in-season · 2011
  - `IAMTHEOMEN Player Trades Count`
  - `The Mammalian Aliens Player Trades Count`
  - `whats going on here Player Trades Count`
  - `Fie Player Trades Count`
  - `6 Deuce Larry H2Ovaries Player Trades Count`
  - …(+7 more, vary by team/manager)

### O · Commissioner

**assigned League Management Privileges** — 8× · 0 in-season · 2013–2024
  - `assigned League Management Privileges to scott.`
  - `assigned League Management Privileges to Ill.`
  - `assigned League Management Privileges to Dave.`
  - `assigned League Management Privileges to harry.`
  - `assigned League Management Privileges to Jeff.`
  - …(+3 more, vary by team/manager)

**removed League Management Privileges** — 5× · 1 in-season · 2014–2022
  - `removed League Management Privileges from brian.`
  - `removed League Management Privileges from scott.`
  - `removed League Management Privileges from harry.`
  - `removed League Management Privileges from Dave.`
  - `removed League Management Privileges from Jeff.`

---

## Decisions log (entry-by-entry, user-driven)

**STATUS: categorization COMPLETE (2026-06-14).** All 34 canonical types decided across
entries #1–#31 (some entries cover 2 types). Next phase = implementation (rewrite
`_SETTING_PATTERNS` → tiered classifier + resolution + rephrasing + off/in-season marker +
frontend). Tier rollup:
- **T1 / elevated:** scoring 2010→11 diff · roster (starting + reserve/IR) · Playoff Settings ·
  FAAB switch (2021) · Trade Deadline first-set (2019) · Division realignments (4 events) ·
  Adjusted Pts 2021-Wk17 correction · commissioner handoff-of-power events.
- **T2:** updated playoff teams (missing context) · Waiver Period · Trade Review 2010/11 ·
  Trade Reject Time · Fee/buy-in timeline · Standings Tiebreaker · Post Draft Players ·
  Undroppable List · Time Per Pick eras · updated the Draft Board (ambiguous) · League Schedule
  rebuild (2014) · Logo/Lineup-lock punishment (2012) · Waiver Priority 2018 reorder ·
  per-team Waiver Budget (2022).
- **T3 (collapsed):** scoring 2011–24 hedged · Draft Type/Time/Order/randomized · Reset the
  draft · Trade Review 2023–25 repeats · Trade Deadline 2011 shuffle · Time Per Pick blips ·
  Edit Story/Poll Permission · Player Adds/Trades Count · (and all the individual rows that roll
  up into elevated aggregate events).

Tiers: T1 highlighted · T2 always-shown · T3 collapsed. "SPLIT" = one type renders
as different tiers depending on whether real detail is recoverable. Several entries are
"T3 individually → collapse to ONE elevated (T1/T2) event" via the aggregate-to-elevated-event
pattern (see concept notes).

| # | Entry | Decision | Notes |
|---|-------|----------|-------|
| 1 | updated scoring settings | **SPLIT** | T1 = derived scoring-rule diff (only 2010→2011 exists: ½→full PPR, pass TD 6→4). T3 = hedged note "{actor} edited scoring {date}; specifics not recorded" for 2011–2024 (incl. 2024 in-season). |

### Data gaps surfaced during this process
- **Per-season scoring history not in DB.** `scoring_rules` is a single snapshot copied to
  2011–2025 (identical fingerprint; `created_at` all 2026-05-29). Only 2010 differs. The
  vague "updated scoring settings" headlines for 2011–2024 are **unrecoverable** without an
  upstream per-season scoring scrape (Phase 1). Tracked for the UP program.

| 2 | updated roster positions | **T1 (fully resolved)** | All occurrences now carry concrete before/after — no hedged fallback. Starting-lineup diffs: 2011 (harry) 3 WR → 2 WR + W/R flex; 2016 (Dave) flex W/R → R/W/T. **Reserve/IR-slot diffs (was pending): 2020 (Chris) reserve/IR expanded 1 → 3; 2021 (Chris) reserve/IR 3 → 2.** Labels: "Roster positions" (starting) / "Roster: reserve slots". |
| 3 | Playoff Settings (C1) | **T1** | Carries before/after encoding both bracket weeks + field size, e.g. "Weeks 15 & 16 – 4 teams" → "Weeks 15,16 & 17 – 6 teams". Bracket-weeks half independently corroborated by `matchups` (2010 = wk 15–17; 2011–2020 = wk 14–16; 2021+ = wk 15–17). Label "Playoff format". |
| 4 | updated playoff teams (C2) | **T2 — missing context** | 16×, all in-season (Dec 2010–2017). Commissioner finalizing/seeding the bracket — a symptom of various, sometimes convoluted end-of-season / postseason access-management events. Field size **not derivable** (see data gap below). Kept as its own significant type (affects season outcome); shown with a **"missing context"** marker + actor/date. Reconstructing the exact events is **out of current scope but a valued future enhancement** (see below). **Likely linked to the legacy best-of-3 playoff-access tiebreaker** — see league-knowledge note. |
| 5 | Waiver Type + Waiver Budget (D1+D2) | **T1 — merged** | Same event (2021-08-27, Chris): league switched its waiver system to **FAAB**, budget **$100**. Rendered as one row: "Switched to FAAB waivers ($100 budget)" (was "Resets to Inverse Standings Order"). Pins the [[league-settings-ledger]] waiver→FAAB switch-year = **2021**. Both carry before/after — fully resolvable. |
| 6 | Waiver Period (D3) | **T2** | 1×, in-season (2011-09-12, harry). Shortened waiver claim-processing window 2 days → 1 day. Affects gameplay but not high-importance. Carries before/after. Label "Waiver period". |
| 7 | Trade Review Type (E1) | **SPLIT** | Trade-approval mechanism. T2 = the substantive 2010 (votes→manager veto) & 2011 (veto→no review) transitions. T3 = the 2023/24/25 occurrences (NFL.com resets to "League Votes" each season; commissioner re-selects "No Review" → routine re-confirmation, collapse into one note). Carries before/after. |
| 8 | Trade Deadline (E2) | **SPLIT** | T1 = 2019-11-03 (Jeff) "No Deadline → November 15" — first-ever trade deadline, significant rule change. T3 = the 2011-09-01 same-day net-zero shuffle (Nov 18→25→18). Carries before/after. |
| 9 | Trade Reject Time (E3) | **T2** | 1×, in-season (2010-09-20, harry). Pending-trade processing window 2 days → 1 day. Carries before/after. Label "Trade reject window". |
| 10 | Fee for Joining League (F1) | **T2** | 5×, all off-season (2010–2013). Buy-in timeline: $0→$20 (2010)→$100→$125 (2012)→$150→$125 (2013). Fun-but-not-critical; flat T2 as one always-shown timeline. **Last entry (2013-08-05, $150→$125) gets a note: this was the last time the buy-in was recorded on the NFL.com platform — later buy-in history is incomplete/unrecorded** (see data gap). Carries before/after. |
| 11 | Standings Tiebreaker (G1) | **T2** | 2×, both in-season (2014, 2018). Both "Head to Head Record → Points For" (NFL.com resets to H2H default each season; commissioner re-selects PF → 2018 is re-confirmation, not a flip). Flat T2. **NOT fully informed** — the recorded entries are only the tail of a larger transition; see the league-knowledge note below on the **legacy best-of-3 tiebreaker**. Corroborates [[phase2-standings-tiebreak]] (PF-based from 2014 on). |
| 12 | Post Draft Players (H1) | **T2** | 1×, 2010 (harry). "Follow Waiver Rules → Free Agents" — undrafted players become open FA pickups. **Originating standard, never changed since** → nice to surface visually (see concept note). Carries before/after. |
| 13 | Undroppable List (H2) | **T2** | 1×, 2010 (harry). "NFL.com Fantasy → None" — any player can be dropped. **Originating standard, never changed since** → surface visually. Carries before/after. |
| 14 | Draft Type (I1) | **T3** | 13×, all off-season, always "offline → live". NFL.com defaults Draft Type to "offline" each season; commissioner flips to "live" to open the online room → routine annual setup, **no real variation**, collapse into the per-season minor bucket. (Earlier "offline→live is real" hint was wrong.) **BUT see note:** at least one year had a genuine **in-person draft** later entered manually — possibly deducible. |
| 15 | Draft Time (J1) | **T3** | 23×, scheduling; many net-zero back-and-forth nudges. Collapse into minor bucket. |
| 16 | Draft Order (J2) | **T3** | 12×, `snake→custom` ×11 / `random→custom` ×1 — annual default-reset; league always uses custom. Collapse. |
| 17 | randomized Custom Draft Order (J3) | **T3** | 3×, action that shuffles custom draft slots. Collapse. |
| 18 | Time Per Pick (J4) | **SPLIT** | T2 = the two real pace eras: **15s clock (2017–2019)** then **120s clock (2020–present)**. T3 = transient 300s (2020, reverted 5 days) & 90s (2023, reverted 9 days). All carry before/after. **Circumstantial:** a 15s clock is implausibly short for a real live online draft (12 managers × 15 rounds) → weak supporting evidence that **2017–2019 drafts may have been conducted offline / entered manually** (⚠️ uncertain, not provable from data — see in-person-draft note). |
| 19 | Reset the draft (J5) | **T3** | 4× (2014, 2018, 2019, 2025), commissioner cleared/reset draft. T3 **by default**, but revisit per-occurrence if the in-person-draft investigation (entry 14 note) deduces one represents an important moment or pairs with a significant change. (2018-09-02 Reset coincides with the 2018 "updated the Draft Board" — see #20.) |
| 20 | updated the Draft Board (J6) | **T2 — ambiguous (investigated, unresolved)** | 1× only (2018-09-02, Jeff), same day as a Reset the draft. **Investigated 2026-06-14:** draft-pick data carries no real timing (synthetic Aug-1 placeholders, empty extra_data, notes = round/pick only) → **no solid evidence** of what this represented or whether 2018 was an offline draft. Per user direction, **left ambiguous at T2 / missing-context** rather than over-claiming. Revisit only if upstream draft-timing data ever lands. |
| 21 | League Schedule for Week N (K1) | **T3 individually → collapse to ONE T2 event** | 13× same day (2014-09-02, scott), Weeks 1–13 = full regular season rebuilt by hand before 2014 kickoff. The 13 rows are T3 individually but **aggregate to a single significant T2 event** for the 2014 season: "Rebuilt the Week 1–13 schedule." Neutral act / missing context (headline-only, before-state not recoverable), but stands out — only schedule rebuild in league history. **Introduces the "aggregate-to-elevated-event" display pattern** (see concept note). |
| 22 | Division (per-team) (L1) | **T3 individually → collapse to ONE T1 event per realignment** | 36× across 4 off-season clusters: 2011-08-06 (harry, 12), 2013-08-02 (sully, 12), 2015-08-12 (scott, 6), 2020-08-11 (Chris, 6). 2 divisions ('1'/'2'). Individual per-team rows T3, but each cluster collapses to a **T1** "Division realignment" event for its season — **division changes are major**. Carries before/after (state who moved). Competitive relevance: division/conference games fed the legacy best-of-3 tiebreaker ([[phase2-standings-tiebreak]]). Aggregate-to-elevated-event pattern, elevated to **T1**. |
| 23 | Edit Story Permission (M1) | **T3** | 32×, granting members rights to edit league "stories." Routine admin perms; collapse. |
| 24 | Edit Poll Permission (M2) | **T3** | 11×, granting members rights to edit league polls. Routine admin perms; collapse. |
| 25 | Logo Lock + Lineup Changes Lock (M3) | **T3 individually → ONE T2 event (FULLY DEDUCED)** | 4× toggles, 2012-09-26→28 (in-season), by **sully (commissioner)** against **mike**. **Deduced:** mike named his team a slur targeting sully (`SulladisaN1GGER` / `Sulladisa4kingN1GGER`; canonical 2012 name "Sulladismichaelbushleague"); sully retaliated by **locking mike's team logo and lineup-change ability** mid-season (real competitive penalty). Corroborated by mike's recurring sully-mocking names (2013 "Salty Caramel Sullad", 2014 "IStoleSulladsPick"). T2 single event: "Commissioner's playful punishment — locked {mike}'s logo & lineup after an offensive team name aimed at the commish." |
| 26 | Waiver Priority per-team (M4) | **T3 individually → ONE T2 event (mechanics deduced, cause not recorded)** | 12×: 2017-09-03 (off, trivial 2-team swap 5↔6 = correction) + **2018-10-09 (in-season, 10 entries)**. **Deduced mechanics:** one team ("Doughy Donald's Rushin' Trolls") moved **12 → 3** in waiver order; teams previously 3–11 each shifted +1 → a single manual move up the order by commissioner Jeff. **Cause not recorded** (likely a correction/compensation). Owner-mapping unreliable (mid-season names drift from canonical). T2 single event for 2018: "Commissioner manually reordered waivers — moved one team from last to 3rd; reason not recorded." |
| 27 | Waiver Budget per-team (M5) | **T2 (mechanics clear, cause not recoverable)** | 1×, 2022-09-16 (in-season), commissioner **Dan** raised team "Ice Station Zebra"'s FAAB budget **39 → 76** mid-season. **Cause not recoverable** — FAAB bid/spend amounts are not stored (extra_data null; see data gap). Most likely a correction/refund. T2 with brief honest note: "Commissioner adjusted a team's remaining FAAB budget mid-season (39→76); reason not recorded — likely a correction." |
| 28 | Adjusted Pts For Week N (N1) | **T1 — ONE event, re-attribute to 2021** | 4× (2022-01-16, Dan): 4 teams' **Week 17 scores raised from 0.00** (→ 55.26 / 28.68 / 23.4 / 5.60) — a scoring glitch fixed by hand in the **2021 championship week**. Outcome-affecting → T1, aggregated to one event: "Commissioner corrected Week 17 scores for 4 teams (each from 0) after a scoring glitch." **Re-attribute to season 2021** (filed under 2022 — data quirk, see gap). **Verified 2026-06-14:** the 2021 championship was scott def. DJ — **NOT a Jeff–sully matchup**, so the "needs further revision" condition does **not** fire; standard T1 representation stands until more context emerges. |
| 29 | Player Adds Count (N2) | **T3** | 12× (2011-08-18, harry), zeroing each team's season add counter (`16→0`). Pre-season counter reset; collapse. |
| 30 | Player Trades Count (N3) | **T3** | 12× (2011-08-18, harry), zeroing each team's season trade counter. Pre-season counter reset; collapse. |
| 31 | League Management Privileges — assigned + removed (O1+O2) | **T3 individually → T1 handoff-of-power events** | 13× total (8 assigned 2013–2024, 5 removed 2014–2022). Individual grants/revokes T3, but collapse into **T1** events marking the **essential commissioner succession** (handoff of power), filtering out temporary co-manager grants as noise (e.g. 2018 harry assigned-then-removed; brian removed 2014). Essential lineage ~ harry → sully → scott → Dave → Jeff → Chris → Dan → Rob. **Cross-reference the existing Commissioner history** (`commissioners` table / `docs/archive/commissioner-history.md`) — these setting_changes are its source data; don't duplicate the full governance timeline in /seasons/. Aggregate-to-elevated-event pattern (→ T1). |

### Key data findings (resolution method)
- **Method:** headline-only entries ("X updated Y") can be resolved by diffing the real
  state tables across seasons and aligning on the headline's `executed_at` + `notes` (actor).
- **Roster slots ARE observable** from `team_rosters.roster_slot` (per player/week/season,
  `is_starter`). Starting-lineup structure: 2010 = QB·RB×2·WR×3·TE·K·DEF (no flex);
  2011–2015 = 2 WR + **W/R flex**; 2016–present = flex widened to **R/W/T**. Headline dates
  align exactly (2011-07-25 harry; 2016-08-24 Dave).
- **Reserve/IR slot capacity IS observable** from max simultaneous `RES`-slot occupancy per
  team per season: hard ceiling of **1 for 2011–2019** (nine straight seasons, every team) →
  **3 in 2020** (Chris; COVID-era — NFL.com added a COVID-19 reserve alongside IR; the 1→3 is
  hard data, the COVID cause is inferred) → **2 from 2021 on** (Chris). Bench (`BN`) is a flat
  6 at week 1 every season (stray week-1 "7"s appear in no-edit years too → reconstruction
  noise, not a capacity change).
- **Playoff bracket weeks ARE observable** from `matchups` (which weeks carry `is_playoff=1`):
  2010 = 15–17, 2011–2020 = 14–16, 2021+ = 15–17. This corroborates the C1 "Playoff Settings"
  text and is independently derivable.
- **Playoff field size is NOT** (see data gap below): can't infer how many teams made the
  championship bracket.
- **Scoring is NOT** (see data gap above): `scoring_rules` flat snapshot 2011–2025.

### Additional data gaps surfaced
- **Season mis-attribution: 2021 Week-17 corrections filed under 2022 (N1).** The 4 `Adjusted
  Pts For Week 17` rows are dated 2022-01-16 and concern the **2021 season's championship week**
  (2021 playoffs = wk 15–17), yet carry season_id=2022. Display must re-attribute to 2021. A
  setting_change's season_id can lag the season it actually concerns when the action happens in
  the Jan offseason window — check `effective_week` + date, not just season_id.
- **FAAB bid/spend amounts not stored.** `transactions.extra_data` is null for `waiver_add`
  rows → no per-claim bid amounts. Blocks reconstructing why a team's FAAB budget changed
  (M5, 2022 Ice Station Zebra 39→76). Waiver *dates* are real and usable.
- **Mid-season team names drift from canonical.** `teams.team_name` is the end-of-season name;
  mid-season names appear only inside setting_change descriptions, so per-team entries from
  mid-season (e.g. M4 waiver-priority 2018) can't be reliably owner-mapped by name.
- **Draft-pick timing is synthetic (all seasons).** Every season's 180 draft picks (15 rds ×
  12 teams) are stamped a placeholder span Aug 1 00:00:01→00:03:00 (1 sec apart); `extra_data`
  empty; notes only encode round/pick/overall. **No real draft timing exists** in the DB →
  cannot deduce live-online vs in-person/manual drafts from pick data. Blocks the in-person-draft
  deduction (entry 14/J6) via timing; only circumstantial setting-log signals remain.
- **Buy-in history incomplete after 2013 (F1 `Fee for Joining League`).** NFL.com stopped
  recording fee changes after 2013-08-05 ($150→$125). The current/later buy-in is not in the
  data; the timeline ends there with an explanatory note rather than implying $125 is current.
- **Playoff field size not derivable (C2 `updated playoff teams`).** Confirms F-49:
  `matchups.is_consolation` is unpopulated (all 0) and **all 12 teams** appear in
  playoff-flagged weeks every season, so the championship field size (e.g. 4 vs 6 teams)
  cannot be reconstructed from results/standings data. Headline-only → T2 with a
  "missing context" marker.

### League knowledge — legacy tiebreaker system (user-provided, 2026-06-14)
Context the setting_change data alone does **not** capture, supplied by the commissioner:
- **Legacy era (year one or possibly later):** standings ties used a **best-of-3** test
  comparing three categories — (1) head-to-head record, (2) points for, (3) W-L record in
  **conference (division) games**. A team that beat its opponent in **2 of the 3** won the
  tiebreaker.
- This best-of-3 was originally used **for playoff access only** — which the commissioner
  notes **may explain the timing of some `updated playoff teams` (C2) manager-activity
  entries** (commissioner manually applying the multi-factor tiebreaker to set the field).
- **Regular-season** standings in that era were broken by a **single** factor — one of
  total W-L, points for, or another determinant the commissioner could **not recall
  specifically** (⚠️ uncertain — do not assert).
- **Current era:** the legacy best-of-3 was **scrapped**; **both** regular-season and
  postseason standings ties are now decided by **total points scored for the season** (PF).
  The recorded 2014/2018 "H2H → Points For" entries are the visible tail of this shift.
- ⚠️ The **exact switch year** for scrapping best-of-3 is not pinned by the data; 2014 is the
  first *recorded* PF selection but the transition may predate the recorded entries. Aligns
  with [[phase2-standings-tiebreak]]'s "don't re-implement old best-of-3 / pre-2019 caveat."
  Reconstructing exact years is a **future enhancement**, not current scope.

### Concept — "aggregate-to-elevated-event" (reusable display idea, user-raised 2026-06-14)
A cluster of entries that are each **individually T3** (routine, repetitive) can together
constitute **one significant event** worth showing at **T2** — collapse the many rows into a
single elevated event for that season, rather than burying them all in the minor bucket.
The elevated tier can be T2 **or T1** depending on significance. Instances: the 13 `League
Schedule for Week N` edits (2014) → one **T2** "Rebuilt the schedule" event; the 36 per-team
`Division` changes → one **T1** "Division realignment" event per same-day cluster (4 of them).
Distinct from a plain T3 collapse (which stays minor) and from "originating standards" (single
founding settings). Applies wherever same-day/same-type bursts represent a deliberate single action.

### Concept — "originating standards" (reusable display idea, user-raised 2026-06-14)
Some settings were established once (typically 2010 founding setup) and **have never
changed since**. The user wants these surfaced **T2 / visually**, not buried — seeing a rule
that has held for the league's entire history is itself valuable. Candidates beyond H1/H2:
Post Draft Players, Undroppable List (confirmed T2), and possibly other single-occurrence
founding configs. When implementing, consider a small "in place since {year}" affordance.

### Future-enhancement note (out of current scope)
- **Deduce the in-person ("offline") draft year(s).** At least one year in league history the
  draft was conducted **in person** and the results entered **manually** into the NFL.com
  platform afterward by the commissioner. The `Draft Type='offline'` setting may genuinely be
  true for those year(s) rather than a default-reset artifact. It **might be deducible** by
  matching manual league-manager activity patterns (e.g. draft-pick entry timing/signatures,
  `Reset the draft` / `updated the Draft Board` entries) to particular year(s) with a degree of
  certainty. **Update 2026-06-14:** the timing approach is **blocked** — draft-pick timestamps
  are synthetic (see data gap). The only remaining signals are circumstantial and live in the
  setting_change log itself: the **15s pick clock (2017–2019)** is implausibly short for a real
  online draft (weak evidence those years were offline/manual), plus `Reset the draft` /
  `updated the Draft Board` actions. Not provable without upstream draft-timing data; defer.
- **Reconstruct postseason access-management events behind C2.** The 16 `updated playoff
  teams` entries are symptoms of end-of-season / postseason access changes that materially
  affect season outcomes. The user values eventually contextualizing these fully (who, what,
  why per occurrence). Tracked as a future enhancement; not in this redesign's scope.
