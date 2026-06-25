"""League-history read models.

This module turns existing Phase 1 facts into product-facing league context.
It does not invent missing rules/settings; unavailable or inferred facts are
labelled in the payload so the UI can keep caveats next to affected data.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import (
    Matchup,
    Owner,
    PlayerStatsScored,
    ScoringRule,
    Season,
    Team,
    TeamRoster,
)
from sqlalchemy import distinct, func, select

from ff_dashboard.analytics.bracket import season_sacko_map
from ff_dashboard.analytics.common import (
    displayed_seasons,
    owner_name_map,
    played_season_ids,
    require_league,
)
from ff_dashboard.analytics.curated_events import curated_events_by_year
from ff_dashboard.analytics.historical_divisions import historical_division_season
from ff_dashboard.analytics.historical_team_names import (
    period_team_name,
    period_team_name_by_slot,
)
from ff_dashboard.analytics.league_changes import (
    _load_raw,
    classify,
    setting_change_events,
)

# Tier for state-table-derived changes (the setting_change classifier sets its own).
_CATEGORY_TIER: dict[str, str] = {
    "roster_slots": "T1",
    "scoring_rules": "T1",
    "playoffs": "T1",
    "league_size": "T1",
    "scoring_provenance": "T3",
    "data_quality": "T3",
    "schedule": "T2",
    "standings": "T2",
    "waiver": "T2",
    "participants": "T1",  # a manager joining/leaving is a major event in a 12-team league
    "divisions": "T1",  # adding/dropping/restructuring divisions changes schedule + seeding
}

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _team_ref(team: Team | None, owners: dict[int, str | None]) -> dict[str, Any] | None:
    if team is None:
        return None
    return {
        "team_id": int(team.team_id),
        "team_name": period_team_name(team),
        "owner_id": int(team.owner_id),
        "owner_name": owners.get(int(team.owner_id)),
    }


def _teams_by_id(session: Session) -> dict[int, Team]:
    rows = session.execute(select(Team)).scalars().all()
    return {int(t.team_id): t for t in rows}


def _scored_season_ids(session: Session) -> set[int]:
    rows = session.execute(select(distinct(PlayerStatsScored.season_id))).scalars().all()
    return {int(sid) for sid in rows}


def _league_sizes(session: Session) -> dict[int, int]:
    """Active league size, excluding known inactive/artifact season teams.

    The live DB can carry extra season-team rows from historical NFL.com artifacts.
    The actual league size is the count of teams with standings/rank data; for an
    in-progress season before standings exist, fall back to raw season-team rows.
    """
    rows = session.execute(
        select(
            Team.season_id,
            func.count(Team.team_id),
            func.count()
            .filter(
                (Team.final_rank.is_not(None))
                | (Team.regular_season_wins.is_not(None))
                | (Team.regular_season_points_for.is_not(None))
            )
            .label("standing_count"),
        ).group_by(Team.season_id)
    )
    return {
        int(season_id): int(standing_count or raw_count)
        for season_id, raw_count, standing_count in rows
    }


def _raw_league_sizes(session: Session) -> dict[int, int]:
    rows = session.execute(
        select(Team.season_id, func.count(Team.team_id)).group_by(Team.season_id)
    )
    return {int(season_id): int(count) for season_id, count in rows}


def _season_source(season: Season, scored_ids: set[int]) -> dict[str, str | bool]:
    if int(season.season_id) in scored_ids:
        return {
            "scoring_provenance": "nflverse_reconstructed",
            "verification_status": "verification_pending",
            "source": "computed_from_scored_player_rows",
        }
    return {
        "scoring_provenance": "nfl_com_authoritative_total",
        "verification_status": "known_source_gap",
        "source": "team_totals_without_player_reconstruction",
    }


def _change(
    category: str,
    title: str,
    summary: str,
    *,
    before: str | None = None,
    after: str | None = None,
    source: str = "derived_from_db",
    certainty: str = "verified",
    changed_at: str | None = None,
    participants_joined: list[str] | None = None,
    participants_left: list[str] | None = None,
    description_gap: bool = False,
    tier: str | None = None,
    human_label: str | None = None,
    phase: str | None = None,
    event_group_key: str | None = None,
    missing_context: bool = False,
    members: list[dict[str, Any]] | None = None,
    canonical_type: str | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "title": title,
        "summary": summary,
        "before": before,
        "after": after,
        "source": source,
        "certainty": certainty,
        "changed_at": changed_at,
        "participants_joined": participants_joined,
        "participants_left": participants_left,
        "description_gap": description_gap,
        "tier": tier or _CATEGORY_TIER.get(category, "T2"),
        "human_label": human_label or title,
        "phase": phase,
        "event_group_key": event_group_key,
        "missing_context": missing_context or description_gap,
        "members": members or [],
        "canonical_type": canonical_type,
    }


def _format_weeks(reg_weeks: int | None, playoff_weeks: int | None) -> str:
    if reg_weeks is None and playoff_weeks is None:
        return "unavailable"
    if reg_weeks is None:
        return f"? regular + {playoff_weeks} playoff"
    if playoff_weeks is None:
        return f"{reg_weeks} regular + ? playoff"
    return f"{reg_weeks} regular + {playoff_weeks} playoff"


def _fmt_rule_value(rule: ScoringRule) -> str:
    text = rule.raw_text
    if text:
        return text
    if rule.flat_points is not None:
        return f"{rule.flat_points:g} points"
    if rule.points_per_unit is not None and rule.unit_size:
        return f"{rule.points_per_unit:g} per {rule.unit_size:g}"
    return "present"


def _rule_key(rule: ScoringRule) -> tuple[Any, ...]:
    return (rule.category, rule.stat_key, rule.threshold_min, rule.threshold_max)


def _rule_signature(rule: ScoringRule) -> tuple[Any, ...]:
    return (
        rule.points_per_unit,
        rule.unit_size,
        rule.flat_points,
        rule.raw_text,
    )


def _scoring_rules_by_season(session: Session) -> dict[int, dict[tuple[Any, ...], ScoringRule]]:
    rows = session.execute(select(ScoringRule).order_by(ScoringRule.season_id)).scalars()
    by_season: dict[int, dict[tuple[Any, ...], ScoringRule]] = defaultdict(dict)
    for rule in rows:
        by_season[int(rule.season_id)][_rule_key(rule)] = rule
    return by_season


def _scoring_rule_changes(
    season: Season,
    previous: Season | None,
    rules_by_season: dict[int, dict[tuple[Any, ...], ScoringRule]],
) -> list[dict[str, str | None]]:
    if previous is None:
        return []
    current_rules = rules_by_season.get(int(season.season_id), {})
    previous_rules = rules_by_season.get(int(previous.season_id), {})
    if not current_rules or not previous_rules:
        if current_rules != previous_rules:
            return [
                _change(
                    "scoring_rules",
                    "Scoring-rule availability changed",
                    "The scoring-rules table is present for one adjacent season but not the other.",
                    before=f"{len(previous_rules)} rules",
                    after=f"{len(current_rules)} rules",
                    certainty="source_limited",
                )
            ]
        return []

    changes: list[dict[str, str | None]] = []
    for key in sorted(set(current_rules) | set(previous_rules)):
        current = current_rules.get(key)
        prior = previous_rules.get(key)
        if current is None or prior is None:
            label = ": ".join(str(part) for part in key[:2])
            changes.append(
                _change(
                    "scoring_rules",
                    "Scoring rule added" if prior is None else "Scoring rule removed",
                    label,
                    before=_fmt_rule_value(prior) if prior is not None else None,
                    after=_fmt_rule_value(current) if current is not None else None,
                )
            )
        elif _rule_signature(current) != _rule_signature(prior):
            label = current.raw_text or f"{current.category} {current.stat_key}".replace("_", " ")
            changes.append(
                _change(
                    "scoring_rules",
                    "Scoring rule changed",
                    label,
                    before=_fmt_rule_value(prior),
                    after=_fmt_rule_value(current),
                )
            )
    return changes[:8]


def _slot_label(slot: str) -> str:
    labels = {"DEF": "D/ST", "W/R": "WR/RB flex", "R/W/T": "RB/WR/TE flex", "BN": "bench"}
    return labels.get(slot, slot)


def _slot_signature(parts: Mapping[str, int]) -> str:
    order = ("QB", "RB", "WR", "TE", "W/R", "R/W/T", "K", "DEF")
    items = [(slot, parts[slot]) for slot in order if parts.get(slot)]
    items.extend((slot, count) for slot, count in sorted(parts.items()) if slot not in order)
    return ", ".join(f"{count} {_slot_label(slot)}" for slot, count in items)


def _roster_signatures(session: Session) -> dict[int, dict[str, Counter[str]]]:
    rows = session.execute(
        select(
            TeamRoster.season_year,
            TeamRoster.team_id,
            TeamRoster.week,
            TeamRoster.roster_slot,
            TeamRoster.is_starter,
        )
        .where(TeamRoster.roster_slot.is_not(None))
        .order_by(TeamRoster.season_year, TeamRoster.team_id, TeamRoster.week)
    ).all()
    weekly: dict[tuple[int, int, int], dict[str, Counter[str]]] = defaultdict(
        lambda: {"starters": Counter(), "reserve": Counter()}
    )
    reserve_seen: dict[int, Counter[str]] = defaultdict(Counter)
    for year, team_id, week, slot, is_starter in rows:
        if slot is None:
            continue
        bucket = "starters" if is_starter else "reserve"
        weekly[(int(year), int(team_id), int(week))][bucket][str(slot)] += 1
        if not is_starter and slot != "BN":
            reserve_seen[int(year)][str(slot)] = 1

    by_year: dict[int, dict[str, Counter[str]]] = {}
    grouped: dict[int, dict[str, Counter[tuple[tuple[str, int], ...]]]] = defaultdict(
        lambda: {"starters": Counter(), "reserve": Counter()}
    )
    for (year, _team_id, _week), sigs in weekly.items():
        for bucket in ("starters", "reserve"):
            grouped[year][bucket][tuple(sorted(sigs[bucket].items()))] += 1
    for year, buckets in grouped.items():
        by_year[year] = {"reserve": reserve_seen.get(year, Counter())}
        if buckets["starters"]:
            by_year[year]["starters"] = Counter(dict(buckets["starters"].most_common(1)[0][0]))
        else:
            by_year[year]["starters"] = Counter()
    return by_year


def _slot_diff_summary(prior: Counter[str], current: Counter[str]) -> str:
    """Human-readable diff showing only what changed between two slot counters."""
    all_slots = sorted(set(prior) | set(current))
    parts = []
    for slot in all_slots:
        p = prior.get(slot, 0)
        c = current.get(slot, 0)
        if p == c:
            continue
        label = _slot_label(slot)
        if p == 0:
            parts.append(f"+{c} {label}")
        elif c == 0:
            parts.append(f"-{p} {label}")
        elif c > p:
            parts.append(f"{label}: {p}→{c}")
        else:
            parts.append(f"{label}: {p}→{c}")
    return "; ".join(parts) if parts else "lineup reordered"


def _roster_changes(
    season: Season,
    previous: Season | None,
    roster_sigs: dict[int, dict[str, Counter[str]]],
) -> list[dict[str, Any]]:
    if previous is None:
        return []
    current = roster_sigs.get(int(season.year), {})
    prior = roster_sigs.get(int(previous.year), {})
    changes: list[dict[str, Any]] = []
    if current.get("starters") != prior.get("starters") and current.get("starters"):
        prior_starters = prior.get("starters", Counter())
        curr_starters = current["starters"]
        changes.append(
            _change(
                "roster_slots",
                "Starting lineup changed",
                _slot_diff_summary(prior_starters, curr_starters),
            )
        )
    current_reserve = {
        k: v for k, v in current.get("reserve", Counter()).items() if k not in {"BN"}
    }
    prior_reserve = {k: v for k, v in prior.get("reserve", Counter()).items() if k not in {"BN"}}
    if current_reserve != prior_reserve:
        changes.append(
            _change(
                "roster_slots",
                "Reserve/IR slots changed",
                _slot_diff_summary(Counter(prior_reserve), Counter(current_reserve)),
            )
        )
    return changes


def _active_owner_sets(session: Session) -> dict[int, set[int]]:
    rows = session.execute(
        select(Season.year, Team.owner_id)
        .join(Team, Team.season_id == Season.season_id)
        .where(
            (Team.final_rank.is_not(None))
            | (Team.regular_season_wins.is_not(None))
            | (Team.regular_season_points_for.is_not(None))
        )
        .group_by(Season.year, Team.owner_id)
        .order_by(Season.year, Team.owner_id)
    ).all()
    by_year: dict[int, set[int]] = defaultdict(set)
    for year, owner_id in rows:
        by_year[int(year)].add(int(owner_id))
    return by_year


def _owner_names(owner_ids: set[int], owners: dict[int, str | None]) -> str:
    return ", ".join(
        sorted({owners.get(owner_id) or f"Owner {owner_id}" for owner_id in owner_ids})
    )


def _participant_changes(
    season: Season,
    previous: Season | None,
    owner_sets: dict[int, set[int]],
    owners: dict[int, str | None],
) -> list[dict[str, Any]]:
    if previous is None:
        return []
    current = owner_sets.get(int(season.year), set())
    prior = owner_sets.get(int(previous.year), set())
    if not current or not prior or current == prior:
        return []
    entered = current - prior
    left = prior - current
    entered_names = sorted({owners.get(oid) or f"Owner {oid}" for oid in entered})
    left_names = sorted({owners.get(oid) or f"Owner {oid}" for oid in left})
    summary_bits = []
    if entered_names:
        summary_bits.append(f"Joined: {', '.join(entered_names)}")
    if left_names:
        summary_bits.append(f"Left: {', '.join(left_names)}")
    return [
        _change(
            "participants",
            "Manager change",
            "; ".join(summary_bits),
            participants_joined=entered_names if entered_names else None,
            participants_left=left_names if left_names else None,
            certainty="identity_source_limited",
        )
    ]


def _owner_aliases(raw: Any) -> list[str]:
    """Normalize historical alias payloads into display aliases.

    Older/upstream data may store alias provenance as a dict such as
    ``{"display_names": [...]}``; the dashboard API exposes a stable list.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, Mapping):
        values = raw.get("display_names") or raw.get("aliases") or raw.get("names") or []
        if isinstance(values, list):
            return [str(item) for item in values if item]
        if isinstance(values, str):
            return [values]
    return []


def league_timeline(session: Session) -> dict[str, Any]:
    """Season-by-season context for the league museum timeline."""
    league = require_league(session)
    seasons = list(displayed_seasons(session, league.league_id))
    owners = owner_name_map(session)
    teams = _teams_by_id(session)
    sizes = _league_sizes(session)
    raw_sizes = _raw_league_sizes(session)
    scored_ids = _scored_season_ids(session)
    scoring_rules = _scoring_rules_by_season(session)
    roster_sigs = _roster_signatures(session)
    active_owner_sets = _active_owner_sets(session)
    waiver_systems = _waiver_systems(session, [int(s.year) for s in seasons])
    sacko_map = season_sacko_map(session)

    rows: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    previous_season: Season | None = None
    for season in seasons:
        reg_weeks = season.regular_season_weeks
        playoff_weeks = season.playoff_weeks
        league_size = sizes.get(int(season.season_id), 0)
        raw_league_size = raw_sizes.get(int(season.season_id), league_size)
        division_structure = _division_structure(int(season.year))
        source = _season_source(season, scored_ids)
        details: list[dict[str, str | None]] = []
        if previous is not None and previous["league_size"] != league_size:
            details.append(
                _change(
                    "league_size",
                    "Active league size changed",
                    "Active league size is based on teams with standings data, not inactive artifacts.",
                    before=f"{previous['league_size']} teams",
                    after=f"{league_size} teams",
                )
            )
        if previous is not None and (
            previous["regular_season_weeks"] != reg_weeks
            or previous["playoff_weeks"] != playoff_weeks
        ):
            details.append(
                _change(
                    "schedule",
                    "Season calendar changed",
                    "Regular-season or playoff-week count changed from the prior season.",
                    before=_format_weeks(
                        previous["regular_season_weeks"], previous["playoff_weeks"]
                    ),
                    after=_format_weeks(reg_weeks, playoff_weeks),
                )
            )
        if previous is not None and previous["is_scored"] != (int(season.season_id) in scored_ids):
            details.append(
                _change(
                    "scoring_provenance",
                    "Scoring provenance changed",
                    "Player-level scoring availability changed for this season.",
                    before=str(previous["scoring_provenance"]).replace("_", " "),
                    after=str(source["scoring_provenance"]).replace("_", " "),
                    certainty="source_limited",
                )
            )
        if previous is not None and previous["division_structure"] != division_structure:
            before = str(previous["division_structure"])
            after = division_structure
            if before == "No divisions":
                title = "Divisions introduced"
            elif after == "No divisions":
                title = "Divisions removed"
            else:
                title = "Divisions restructured"
            details.append(
                _change(
                    "divisions",
                    title,
                    "The league's division structure changed from the prior season; "
                    "this reshapes the schedule and standings groupings.",
                    before=before,
                    after=after,
                )
            )
        details.extend(_scoring_rule_changes(season, previous_season, scoring_rules))
        details.extend(_roster_changes(season, previous_season, roster_sigs))
        details.extend(_participant_changes(season, previous_season, active_owner_sets, owners))
        if raw_league_size > league_size:
            details.append(
                _change(
                    "data_quality",
                    "Inactive/artifact teams excluded",
                    (
                        f"Raw season-team rows include {raw_league_size - league_size} extra "
                        f"team record(s); active league size remains {league_size}."
                    ),
                    before=f"{raw_league_size} raw team rows",
                    after=f"{league_size} active teams",
                    certainty="source_limited",
                )
            )
        changes = {
            "league_size_changed": previous is not None and previous["league_size"] != league_size,
            "schedule_changed": previous is not None
            and (
                previous["regular_season_weeks"] != reg_weeks
                or previous["playoff_weeks"] != playoff_weeks
            ),
            "scoring_availability_changed": previous is not None
            and previous["is_scored"] != (int(season.season_id) in scored_ids),
            "details": details,
        }
        row = {
            "season_id": int(season.season_id),
            "season_year": int(season.year),
            "status": season.status,
            "league_size": league_size,
            "regular_season_weeks": reg_weeks,
            "playoff_weeks": playoff_weeks,
            "championship_week": (reg_weeks + playoff_weeks)
            if reg_weeks and playoff_weeks
            else None,
            "champion": _team_ref(teams.get(int(season.champion_team_id)), owners)
            if season.champion_team_id is not None
            else None,
            "runner_up": _team_ref(teams.get(int(season.runner_up_team_id)), owners)
            if season.runner_up_team_id is not None
            else None,
            "last_place": _team_ref(teams.get(int(season.last_place_team_id)), owners)
            if season.last_place_team_id is not None
            else None,
            # The Sacko (toilet-bowl loser) — derived where the bracket distinguishes
            # the consolation half, else the recorded last-place team (``source``).
            "sacko": (
                {
                    **(_team_ref(teams.get(int(sacko_row["team_id"])), owners) or {}),
                    "source": sacko_row["source"],
                }
                if (sacko_row := sacko_map.get(int(season.season_id))) is not None
                else None
            ),
            "is_scored": int(season.season_id) in scored_ids,
            "division_structure": division_structure,
            "schedule_source": "scraped"
            if reg_weeks is not None or playoff_weeks is not None
            else "unavailable",
            # Playstyle fingerprint (drives era boundaries; not part of the API shape).
            "ppr_reception_value": _reception_value(scoring_rules.get(int(season.season_id), {})),
            "lineup_flex": _flex_label(
                roster_sigs.get(int(season.year), {}).get("starters", Counter())
            ),
            "waiver_system": waiver_systems.get(int(season.year)),
            **source,
            "changes": changes,
        }
        rows.append(row)
        previous = row
        previous_season = season

    # Setting-change classifier: a STATE headline (roster/scoring) is absorbed when
    # that season already shows a concrete state-table diff of the same category.
    resolved_cats_by_year = {
        int(r["season_year"]): {
            d["category"]
            for d in r["changes"]["details"]
            if d["source"] == "derived_from_db"
            and d["category"] in {"roster_slots", "scoring_rules"}
        }
        for r in rows
    }
    events_by_year = setting_change_events(session, resolved_cats_by_year=resolved_cats_by_year)
    for r in rows:
        r["changes"]["details"].extend(events_by_year.get(int(r["season_year"]), []))

    # Curated narrative events (e.g. the 2022 Hamlin no-contest) have no
    # setting-change transaction; fold them in here so they render via ChangeRow.
    curated_by_year = curated_events_by_year(session)
    for r in rows:
        r["changes"]["details"].extend(curated_by_year.get(int(r["season_year"]), []))

    _assign_era_ids(rows)

    return {
        "league": {
            "league_id": league.league_id,
            "name": league.name,
            "platform": league.platform,
            "start_year": rows[0]["season_year"] if rows else None,
            "current_year": league.current_season_year,
            "season_count": len(rows),
        },
        "seasons": rows,
    }


# ---------------------------------------------------------------------------
# Playstyle fingerprint — per-season state for the rules that define how the game
# is played. Used to cut the league's history into eras (see ``_era_key``).
# ---------------------------------------------------------------------------
def _reception_value(rules: dict[tuple[Any, ...], ScoringRule]) -> float | None:
    """Points per reception (PPR) for a season, or None when not recorded."""
    for rule in rules.values():
        if rule.stat_key == "receptions" and rule.points_per_unit is not None and rule.unit_size:
            return rule.points_per_unit / rule.unit_size
    return None


def _ppr_label(value: float | None) -> str | None:
    if value is None:
        return None
    if abs(value - 1.0) < 1e-6:
        return "Full PPR"
    if abs(value - 0.5) < 1e-6:
        return "Half PPR"
    if value == 0:
        return "Non-PPR"
    return f"{value:g} PPR"


def _flex_label(starters: Counter[str]) -> str | None:
    """The starting-lineup's flex character — the salient lineup playstyle trait."""
    if not starters:
        return None
    if starters.get("R/W/T"):
        return "RB/WR/TE flex"
    if starters.get("W/R"):
        return "WR/RB flex"
    return "No flex"


def _division_structure(year: int) -> str:
    """The season's division *structure* (never its rotating, cosmetic names).

    Sourced from the reviewed ``historical_divisions`` artifact, which covers the
    seasons that had divisions; any other season played as a single table. The
    structure (how many divisions of what size) is the gameplay-significant fact —
    it shapes the schedule and standings — so it is shown as era context, but it
    deliberately does *not* feed ``_era_key`` (the division drop and the FAAB move
    happened a year apart, and splitting on it would orphan a single season).
    """
    season = historical_division_season(year)
    if season is None:
        return "No divisions"
    sizes = [len(division.teams) for division in season.divisions]
    if len(set(sizes)) == 1:
        return f"{len(sizes)} divisions of {sizes[0]}"
    return f"{len(sizes)} divisions ({', '.join(str(size) for size in sizes)})"


def _waiver_class(value: str | None) -> str | None:
    """Map a raw NFL.com waiver-type value to a durable system label."""
    if not value:
        return None
    return "FAAB budget" if "budget" in value.lower() else "Standings-order waivers"


def _waiver_systems(session: Session, years: list[int]) -> dict[int, str]:
    """Per-season waiver system, reconstructed by carrying the last setting forward.

    Only ``waiver_type`` transitions move the state; the value *before* the first
    transition seeds the earlier seasons (the DB records what it was), so nothing
    is invented. Years with no recoverable state are omitted.
    """
    events: list[tuple[int, datetime | None, str | None, str | None]] = []
    for raw in _load_raw(session):
        c = classify(raw)
        if c.canonical_type == "waiver_type":
            events.append((raw.year, raw.executed_at, c.before, c.after))
    if not events:
        return {}
    events.sort(key=lambda e: (e[0], e[1] or datetime.min))
    # Seed pre-history from the first transition's "before" value (the DB records it).
    current = _waiver_class(events[0][2])
    transitions = {year: _waiver_class(after) for year, _at, _before, after in events}
    out: dict[int, str] = {}
    for year in sorted(years):
        if transitions.get(year):
            current = transitions[year]
        if current is not None:
            out[year] = current
    return out


# An era is defined by *playstyle*, not bookkeeping: the few highly-significant
# rules that change how the game is actually played — reception scoring (PPR), the
# starting-lineup flex, and the waiver system. An era is a maximal run of seasons
# sharing that fingerprint, so every boundary marks a real shift (PPR doubling, the
# FLEX appearing, the move to FAAB). Each trait is per-season state proven from the
# DB; a dimension we can't prove is left out of the label, never guessed.
def _era_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _ppr_label(row.get("ppr_reception_value")),
        row.get("lineup_flex"),
        row.get("waiver_system"),
    )


def _era_traits(row: dict[str, Any]) -> list[str]:
    """The era's defining traits, most-salient first, omitting any we can't prove."""
    bits: list[str] = []
    ppr = _ppr_label(row.get("ppr_reception_value"))
    if ppr:
        bits.append(ppr)
    if row.get("lineup_flex"):
        bits.append(row["lineup_flex"])
    if row.get("waiver_system"):
        bits.append(row["waiver_system"])
    return bits


def _era_label(row: dict[str, Any]) -> str:
    traits = _era_traits(row)
    return " · ".join(traits) if traits else f"{row['league_size']}-team league"


def _era_defining_change(row: dict[str, Any], previous: dict[str, Any] | None) -> str:
    """One line naming what shifted at this era's boundary versus the prior era."""
    if previous is None:
        return "Earliest recorded ruleset"
    bits: list[str] = []
    cur_ppr, prev_ppr = (
        _ppr_label(row.get("ppr_reception_value")),
        _ppr_label(previous.get("ppr_reception_value")),
    )
    if cur_ppr and cur_ppr != prev_ppr:
        bits.append(f"{cur_ppr} scoring")
    if row.get("lineup_flex") and row.get("lineup_flex") != previous.get("lineup_flex"):
        bits.append(str(row["lineup_flex"]))
    if row.get("waiver_system") and row.get("waiver_system") != previous.get("waiver_system"):
        bits.append(str(row["waiver_system"]))
    if not bits:
        return "Settings refined"
    text = "; ".join(bits)
    return text[:1].upper() + text[1:]


def _assign_era_ids(rows: list[dict[str, Any]]) -> None:
    """Tag each season row with the id of its contiguous playstyle era.

    An era is a maximal run of seasons sharing ``_era_key`` (PPR, flex, waivers).
    This is the same grouping ``league_eras`` summarises, so the timeline
    ``era_id`` and the ``/eras`` summaries agree by construction.
    """
    era_count = 0
    previous_key: tuple[Any, ...] | None = None
    for row in rows:
        key = _era_key(row)
        if era_count == 0 or key != previous_key:
            era_count += 1
        row["era_id"] = f"era-{era_count}"
        previous_key = key


def league_eras(session: Session) -> dict[str, Any]:
    """Playstyle eras derived from the highly-significant rules the dashboard can prove."""
    timeline = league_timeline(session)
    seasons = timeline["seasons"]
    eras: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    previous_row: dict[str, Any] | None = None

    for row in seasons:
        era_id = row["era_id"]
        if current is None or era_id != current["era_id"]:
            current = {
                "era_id": era_id,
                "label": _era_label(row),
                "defining_change": _era_defining_change(row, previous_row),
                "start_year": row["season_year"],
                "end_year": row["season_year"],
                "season_years": [row["season_year"]],
                "ppr": _ppr_label(row.get("ppr_reception_value")),
                "lineup": row.get("lineup_flex"),
                "waiver_system": row.get("waiver_system"),
                # Division structure is era *context*, not an era-defining trait: resolved
                # to a single value below, or None when the era straddles a change (the
                # inline ``divisions`` change-event names that transition).
                "division_structure": row["division_structure"],
                "_division_structures": {row["division_structure"]},
                "league_size": row["league_size"],
                "regular_season_weeks": row["regular_season_weeks"],
                "playoff_weeks": row["playoff_weeks"],
                "scoring_provenance": row["scoring_provenance"],
                "verification_status": row["verification_status"],
                "certainty": "scraped"
                if row["regular_season_weeks"] is not None
                else "unavailable",
            }
            eras.append(current)
            previous_row = row
        else:
            current["end_year"] = row["season_year"]
            current["season_years"].append(row["season_year"])
            current["_division_structures"].add(row["division_structure"])

    for era in eras:
        structures = era.pop("_division_structures")
        era["division_structure"] = next(iter(structures)) if len(structures) == 1 else None

    changes = [
        {
            "season_year": row["season_year"],
            "league_size_changed": row["changes"]["league_size_changed"],
            "schedule_changed": row["changes"]["schedule_changed"],
            "scoring_availability_changed": row["changes"]["scoring_availability_changed"],
            "details": row["changes"]["details"],
        }
        for row in seasons
        if row["changes"]["league_size_changed"]
        or row["changes"]["schedule_changed"]
        or row["changes"]["scoring_availability_changed"]
        or row["changes"]["details"]
    ]
    return {"league": timeline["league"], "eras": eras, "changes": changes}


def league_overview(session: Session) -> dict[str, Any]:
    """High-level command-center summary."""
    timeline = league_timeline(session)
    eras = league_eras(session)["eras"]
    seasons = timeline["seasons"]
    sizes = [s["league_size"] for s in seasons if s["league_size"]]
    champions = [s for s in seasons if s["champion"] is not None]
    return {
        **timeline["league"],
        "league_size_min": min(sizes) if sizes else None,
        "league_size_max": max(sizes) if sizes else None,
        "completed_seasons": len([s for s in seasons if s["status"] == "completed"]),
        "scored_seasons": len([s for s in seasons if s["is_scored"]]),
        "champions_recorded": len(champions),
        "current_era": eras[-1] if eras else None,
        "data_caveats": [
            {
                "code": "rules_not_fully_scraped",
                "label": "Detailed scoring and roster-slot rules are not yet fully captured.",
                "scope": "rules_and_eras",
            },
            {
                "code": "player_scoring_by_season",
                "label": "Player scoring availability is season-specific and shown per season.",
                "scope": "season_context",
            },
        ],
    }


@dataclass(frozen=True)
class _Game:
    season_id: int
    week: int
    team_id: int
    opponent_team_id: int
    team_score: float
    opponent_score: float
    matchup_id: int
    is_playoff: bool


def _unique_games(session: Session) -> list[_Game]:
    rows = session.execute(
        select(Matchup)
        .where(Matchup.opponent_team_id.is_not(None))
        .order_by(Matchup.season_id, Matchup.week)
    ).scalars()
    seen: set[tuple[int, int, int, int]] = set()
    games: list[_Game] = []
    for m in rows:
        if m.team_score is None or m.opponent_score is None:
            continue
        assert m.opponent_team_id is not None
        low, high = sorted((int(m.team_id), int(m.opponent_team_id)))
        key = (int(m.season_id), int(m.week), low, high)
        if key in seen:
            continue
        seen.add(key)
        games.append(
            _Game(
                season_id=int(m.season_id),
                week=int(m.week),
                team_id=int(m.team_id),
                opponent_team_id=int(m.opponent_team_id),
                team_score=float(m.team_score or 0.0),
                opponent_score=float(m.opponent_score or 0.0),
                matchup_id=int(m.matchup_id),
                is_playoff=bool(m.is_playoff),
            )
        )
    return games


def league_stories(session: Session) -> dict[str, Any]:
    """Backend-computed story cards for the league-history product."""
    owners = owner_name_map(session)
    teams = _teams_by_id(session)
    season_year = {
        int(sid): int(year)
        for sid, year in session.execute(select(Season.season_id, Season.year)).all()
    }
    games = _unique_games(session)

    story_cards: list[dict[str, Any]] = []
    if games:
        blowout = max(games, key=lambda g: abs(g.team_score - g.opponent_score))
        winner_id = (
            blowout.team_id
            if blowout.team_score >= blowout.opponent_score
            else blowout.opponent_team_id
        )
        loser_id = blowout.opponent_team_id if winner_id == blowout.team_id else blowout.team_id
        story_cards.append(
            {
                "story_id": "biggest-blowout",
                "title": "Biggest blowout",
                "available": True,
                "season_year": season_year.get(blowout.season_id),
                "week": blowout.week,
                "matchup_id": blowout.matchup_id,
                "metric_label": "Margin",
                "metric_value": round(abs(blowout.team_score - blowout.opponent_score), 2),
                "primary_team": _team_ref(teams.get(winner_id), owners),
                "secondary_team": _team_ref(teams.get(loser_id), owners),
                "caveat": None,
            }
        )

    close_losses: Counter[int] = Counter()
    for game in games:
        margin = abs(game.team_score - game.opponent_score)
        if 0 < margin <= 5:
            loser = game.team_id if game.team_score < game.opponent_score else game.opponent_team_id
            team = teams.get(loser)
            if team is not None:
                close_losses[int(team.owner_id)] += 1
    if close_losses:
        owner_id, losses = close_losses.most_common(1)[0]
        story_cards.append(
            {
                "story_id": "close-loss-magnet",
                "title": "Close-loss magnet",
                "available": True,
                "season_year": None,
                "week": None,
                "matchup_id": None,
                "metric_label": "Losses by 5 or fewer",
                "metric_value": losses,
                "primary_owner": {"owner_id": owner_id, "display_name": owners.get(owner_id)},
                "caveat": "Regular-season and postseason games are included when present.",
            }
        )
    else:
        story_cards.append(
            {
                "story_id": "close-loss-magnet",
                "title": "Close-loss magnet",
                "available": False,
                "reason": "no_close_losses",
                "metric_label": "Losses by 5 or fewer",
                "metric_value": None,
                "caveat": None,
            }
        )

    weekly_scores: dict[tuple[int, int], list[tuple[int, float, int]]] = defaultdict(list)
    for game in games:
        weekly_scores[(game.season_id, game.week)].append(
            (game.team_id, game.team_score, game.matchup_id)
        )
        weekly_scores[(game.season_id, game.week)].append(
            (game.opponent_team_id, game.opponent_score, game.matchup_id)
        )
    worst_beat: dict[str, Any] | None = None
    for (season_id, week), scores in weekly_scores.items():
        ranked = sorted(scores, key=lambda s: s[1], reverse=True)
        if len(ranked) < 2:
            continue
        high_team, high_score, high_matchup = ranked[0]
        second_team, second_score, second_matchup = ranked[1]
        if high_matchup == second_matchup and high_score > second_score:
            margin = high_score - second_score
            if worst_beat is None or second_score > worst_beat["metric_value"]:
                worst_beat = {
                    "story_id": "worst-beat",
                    "title": "Worst beat",
                    "available": True,
                    "season_year": season_year.get(season_id),
                    "week": week,
                    "matchup_id": second_matchup,
                    "metric_label": "Losing score",
                    "metric_value": round(second_score, 2),
                    "primary_team": _team_ref(teams.get(second_team), owners),
                    "secondary_team": _team_ref(teams.get(high_team), owners),
                    "caveat": f"Lost to the weekly high score by {margin:.2f}.",
                }
    story_cards.append(
        worst_beat
        if worst_beat is not None
        else {
            "story_id": "worst-beat",
            "title": "Worst beat",
            "available": False,
            "reason": "no_second_highest_score_loss",
            "metric_label": "Losing score",
            "metric_value": None,
            "caveat": None,
        }
    )

    # Count period-correct names: the DB's team_name carries the latest canonical
    # label on every past season, so a raw GROUP BY would over-count one name per
    # owner. Resolve each team-season to its season-correct slot name first.
    name_seasons: dict[str, set[int]] = defaultdict(set)
    for t in teams.values():
        name = period_team_name_by_slot(
            season_year.get(int(t.season_id)), t.team_abbrev, t.team_name
        )
        if name is not None:
            name_seasons[name].add(int(t.season_id))
    hall = [
        {"team_name": name, "seasons": len(sids)}
        for name, sids in sorted(name_seasons.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        if len(sids) > 1
    ][:5]
    story_cards.append(
        {
            "story_id": "team-name-hall",
            "title": "Team-name hall of fame",
            "available": bool(hall),
            "reason": None if hall else "no_repeated_team_names",
            "metric_label": "Repeated names",
            "metric_value": len(hall) if hall else None,
            "items": hall,
            "caveat": "Counts season-scoped team names, not durable manager identity.",
        }
    )

    return {"stories": story_cards}


def manager_directory(session: Session) -> dict[str, Any]:
    """Human-manager directory with identity and team-name history."""
    league = require_league(session)
    seasons = {
        int(sid): int(year)
        for sid, year in session.execute(select(Season.season_id, Season.year)).all()
    }
    played = played_season_ids(session)
    teams = session.execute(select(Team).order_by(Team.owner_id, Team.team_id)).scalars().all()
    by_owner: dict[int, list[Team]] = defaultdict(list)
    for team in teams:
        if int(team.season_id) not in played:
            continue
        by_owner[int(team.owner_id)].append(team)

    owners_rows = session.execute(
        select(Owner).where(Owner.league_id == league.league_id).order_by(Owner.display_name)
    ).scalars()
    managers: list[dict[str, Any]] = []
    for owner in owners_rows:
        owner_teams = by_owner.get(int(owner.owner_id), [])
        years = sorted(
            year
            for year in (seasons.get(int(t.season_id)) for t in owner_teams)
            if year is not None
        )
        team_names = sorted(
            {
                name
                for t in owner_teams
                if (
                    name := period_team_name_by_slot(
                        seasons.get(int(t.season_id)), t.team_abbrev, t.team_name
                    )
                )
            }
        )
        managers.append(
            {
                "manager_id": int(owner.owner_id),
                "display_name": owner.display_name,
                "human_name": None,
                "aliases": _owner_aliases(owner.aliases),
                "nfl_user_id": owner.nfl_user_id,
                "active_years": years,
                "joined_year": owner.joined_year,
                "left_year": owner.left_year,
                "is_active": owner.is_active,
                "team_names": team_names,
                "seasons_managed": len(years),
                "identity_source": "nfl_com_owner_record",
            }
        )
    return {"managers": managers}
