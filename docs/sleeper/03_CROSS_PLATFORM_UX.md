# 03 — Cross-Platform UX Rules

**Status:** planned; corrected 2026-11-09 (see `00_UPSTREAM_STATE.md`) · **Repo:** `dz-dashboard` · **Applies to:** every page that shows more than one season
**Builds on:** `docs/06_DESIGN_SYSTEM.md` (tokens, HUD aesthetic) — nothing here adds a new colour family or font.

The goal: someone browsing 2015 and then 2026 should feel they never left the product. The
platform change is history worth noting once, quietly — not a seam that runs through every screen.

---

## 1. The rules

1. **No platform branding.** No Sleeper or NFL logos, brand colours or wordmarks. The era marker is
   a neutral, token-coloured mono label.
2. **One era marker, in three places only:** the season header, the Timeline, and cross-season
   charts (as a boundary line). Nowhere else by default.
3. **Same labels for the same things.** Slot labels, transaction types and stat names come from the
   canonical vocabulary upstream stores (`R/W/T`, `BN`, `RES`, …) and the display mapping the
   dashboard already applies, regardless of what either platform called them (§4).
4. **Same numbers, same format.** League points always show two decimals in both eras; FAAB shows
   `$` whole numbers; records show `W-L-T`.
5. **Gaps look identical regardless of cause.** One `DataGap` affordance; the reason text names the
   capability and the platform plainly.
6. **Provenance is a footnote, not a badge.** "Official", "computed" and "derived" appear as a
   `ProvenanceNote` under a table or chart, not as chips on every row.
7. **New Sleeper-only features extend existing pages.** Failed bids live in the FAAB section that
   already exists; official brackets replace the bracket that already exists. No new nav item is
   added just because the data is new.
8. **Aggregates say what they used.** When a cross-season number excludes or normalizes seasons, a
   one-line `AggregationNote` says so ("Activity counts exclude lineup changes, which Sleeper does
   not record").

## 2. Era marker spec

```
Season header                    Timeline                          Cross-season chart
┌─────────────────────────────┐  2024 ─●─ 2025 ─●─┊─ 2026 ─●─       PF ┤      ╭─╮   ┊ ╭╮
│ 2026 SEASON   · SLEEPER     │                   ┊                    ┤ ╭─╮╭╯ ╰╮  ┊╭╯╰
│ Week 10 of 14 · provisional │        NFL.COM    ┊   SLEEPER          ┤─╯ ╰╯   ╰──┊╯
└─────────────────────────────┘                   moved to Sleeper       2023 2024 2025┊2026
```

- Text: `NFL.COM` / `SLEEPER`, uppercase mono, `--text-muted`, letter-spaced, same size as other
  header metadata. Component: `EraMarker`.
- Boundary: 1px dashed `--border-strong` vertical rule with a top label; drawn by the chart theme,
  not per chart.
- Never coloured by platform. Never animated.

## 3. Gap copy (by capability)

| Capability | Era lacking it | Copy |
|------------|----------------|------|
| `lineup_change_log` | Sleeper | "Lineup-change history isn't available from Sleeper." |
| `setting_change_log` | Sleeper | "Sleeper doesn't publish a settings change log. Current settings are shown." |
| `faab_failed_bids` | NFL.com | "NFL.com didn't record unsuccessful waiver bids." |
| `trades_with_picks_faab` | NFL.com | "NFL.com trades only recorded players." |
| `official_brackets` | NFL.com | Shown, with footnote: "Bracket derived from NFL.com playoff results." |
| `potential_points` official | NFL.com | Footnote: "Potential points computed by this dashboard." |
| `player_status_daily` | NFL.com seasons | `partial`: weekly game status from nflverse reports (2010–2025 covered) |
| `not_yet` (any) | in-progress season | "Not available until this week is final." |
| `not_used` (any) | a season that didn't use the feature (e.g. no divisions in 2026) | **render nothing**: no copy, no `DataGap` (user rule) |

The capability field from upstream is `note`, not `reason`. Provisional (in-progress) data is shown
as current state with a "subject to change" marker, never hidden or counted as final.

Copy lives in one place (`web/src/lib/platform.ts` → `capabilityCopy`) and is sourced from the
BFF's `reason` when present, so wording stays consistent.

## 4. Label vocabulary

**Rule: whatever the dashboard shows for a legacy slot today is the label for that slot in every
era.** Upstream stores Sleeper slots in the legacy vocabulary (`R/W/T`, `W/R`, `RES`, `BN`, `DEF`),
so Sleeper weeks inherit today's display mapping automatically and legacy screens don't change
(the parity rule). Only genuinely new slot types need new display labels.

| Concept | Stored (both eras) | Display |
|---------|--------------------|---------|
| RB/WR/TE flex | `R/W/T` | as today (e.g. "RB/WR/TE flex" in league history, slot column in box score) |
| WR/RB flex | `W/R` | as today |
| Reserve / IR | `RES` | as today |
| Bench / team defense | `BN` / `DEF` | as today (league history shows `DEF` as "D/ST") |
| Superflex, taxi, IDP | `Q/R/W/T`, `TAXI`, `DL`/`LB`/`DB` | **new** labels, added to the same mapping tables in `analytics/` |
| Waiver claim (won / lost) | `waiver_add` (+ `status='failed'` for lost) | "Waiver add" / "Waiver claim — lost" |
| Draft pick / FAAB in a trade | `trade` leg with `player_id NULL`, `extra_data.picks_in/out`, `faab_in/out` | e.g. "2027 Rd 2 pick", "$7 FAAB" |
| Commissioner move | `free_agent_add` / `drop` with `extra_data.by_commissioner` (no separate type upstream) | "Commissioner move" |
| Manager | `owners.display_name` | league display name, never the Sleeper username |

Display mapping stays in `analytics/` (e.g. `league_history.py`, `matchups.py`); the SPA does not
map labels.

## 5. Page-by-page checklist (D8)

For each page, check 2015, 2025 and 2026:

- [ ] Same layout, same components, same empty/gap states
- [ ] Era marker only in the allowed places
- [ ] No `0` where a capability is missing
- [ ] Labels match §4
- [ ] Aggregates spanning 2025→2026 show an `AggregationNote` when they exclude or normalize anything
- [ ] Provisional weeks clearly marked; finalized weeks look identical to legacy weeks
- [ ] Avatars: 2026 avatars come from the upstream asset store, same size and crop as legacy logos
- [ ] Light/dark parity unchanged

Pages: Home, Timeline, Standings (+ power lens), Playoffs, Matchups, Box score, Team, Teams index,
Managers, Manager profile, Rivalries, Pairwise, Records, Players, Player detail, Stats, Draft,
Stories, Viz Lab, Insights Lab, About.
