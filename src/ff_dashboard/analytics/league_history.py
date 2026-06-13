"""League-history read models.

This module turns existing Phase 1 facts into product-facing league context.
It does not invent missing rules/settings; unavailable or inferred facts are
labelled in the payload so the UI can keep caveats next to affected data.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import (
    Matchup,
    Owner,
    PlayerStatsScored,
    ScoringRule,
    Season,
    Team,
    TeamRoster,
    Transaction,
)
from sqlalchemy import distinct, func, select

from ff_dashboard.analytics.common import (
    displayed_seasons,
    owner_name_map,
    played_season_ids,
    require_league,
)
from ff_dashboard.analytics.historical_team_names import (
    period_team_name,
    period_team_name_by_slot,
)

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
            parts.append(f"−{p} {label}")
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


_SETTING_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("waiver", "Waiver/FAAB setting changed", r"(Waiver Type|Waiver Budget|Waiver Period)"),
    ("standings", "Standings tiebreaker changed", r"Standings Tiebreaker"),
    ("schedule", "League schedule edited", r"League Schedule for Week"),
    ("playoffs", "Playoff format setting changed", r"Playoff Settings"),
    ("roster_slots", "Roster positions setting updated", r"updated roster positions"),
    ("scoring_rules", "Scoring settings updated", r"updated scoring settings"),
)


def _setting_changes(session: Session) -> dict[int, list[dict[str, Any]]]:
    rows = session.execute(
        select(Season.year, Transaction.extra_data, Transaction.executed_at)
        .join(Transaction, Transaction.season_id == Season.season_id)
        .where(Transaction.transaction_type == "setting_change")
        .order_by(Season.year, Transaction.transaction_id)
    ).all()
    by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[int, str, str]] = set()
    for year, extra, executed_at in rows:
        raw = extra or {}
        description = raw.get("description") if isinstance(raw, Mapping) else None
        if not description:
            continue
        for category, title, pattern in _SETTING_PATTERNS:
            if not re.search(pattern, str(description), flags=re.IGNORECASE):
                continue
            key = (int(year), category, str(description))
            if key in seen:
                break
            seen.add(key)
            before_after = re.search(r" from '([^']+)' to '([^']+)'", str(description))
            before = before_after.group(1) if before_after else None
            after = before_after.group(2) if before_after else None
            changed_at = executed_at.isoformat() if executed_at is not None else None
            description_gap = before is None and after is None and category in {
                "roster_slots",
                "scoring_rules",
            }
            by_year[int(year)].append(
                _change(
                    category,
                    title,
                    str(description),
                    before=before,
                    after=after,
                    source="nfl_com_transaction_log",
                    changed_at=changed_at,
                    description_gap=description_gap,
                )
            )
            break
    for year, changes in list(by_year.items()):
        schedule_edits = [change for change in changes if change["category"] == "schedule"]
        if len(schedule_edits) <= 1:
            continue
        by_year[year] = [change for change in changes if change["category"] != "schedule"]
        by_year[year].append(
            _change(
                "schedule",
                "League schedule edited",
                f"{len(schedule_edits)} weekly schedule edits recorded in NFL.com transaction log.",
                source="nfl_com_transaction_log",
            )
        )
    return by_year


def _setting_actor(summary: str) -> str:
    """Pull the manager name out of an NFL.com headline edit.

    These descriptions read ``"<name> updated roster positions"`` /
    ``"<name> updated scoring settings"``; the name may be lower-cased upstream.
    """
    match = re.match(r"^(.*?)\s+updated\s+(?:roster positions|scoring settings)\b", summary)
    return match.group(1).strip() if match and match.group(1).strip() else "A manager"


def _resolve_setting_gaps(
    details: list[dict[str, Any]],
    previous_season: Season | None,
) -> list[dict[str, Any]]:
    """Make headline-only NFL.com setting edits informative instead of bare gaps.

    NFL.com logs roster-position and scoring edits as a bare headline ("X updated
    roster positions") with no before/after. For each such gap entry we either:

    * **drop it** when the same season already carries a *derived* structural diff
      of the same category — that concrete diff (e.g. "Starting lineup changed:
      +1 WR") is the real explanation, so the vague headline is redundant noise; or
    * **rewrite it** into an honest fallback that names the actor and states that
      the tracked structure did not move versus the prior season, so the reader
      knows the edit was reverted, cosmetic, or in a setting we don't capture.
    """
    derived_cats = {d["category"] for d in details if d.get("source") == "derived_from_db"}
    prior_year = int(previous_season.year) if previous_season is not None else None
    resolved: list[dict[str, Any]] = []
    for detail in details:
        if not detail.get("description_gap"):
            resolved.append(detail)
            continue
        category = detail["category"]
        if category in derived_cats:
            # A concrete structural diff for this category is already shown this season.
            continue
        actor = _setting_actor(str(detail["summary"]))
        if category == "roster_slots":
            noun, tracked, verb = "roster settings", "starting-lineup structure", "is"
        else:
            noun, tracked, verb = "scoring settings", "scoring rules", "are"
        if prior_year is not None:
            detail["summary"] = (
                f"{actor} edited {noun} on NFL.com, which records only that an edit "
                f"happened — not the specific values. The {tracked} tracked here {verb} "
                f"unchanged from {prior_year}, so the edit was reverted, cosmetic, or "
                f"in a setting the dashboard doesn't capture."
            )
        else:
            detail["summary"] = (
                f"{actor} edited {noun} on NFL.com, which records only that an edit "
                f"happened — not the specific values."
            )
        detail["description_gap"] = False
        detail["certainty"] = "source_limited"
        resolved.append(detail)
    return resolved


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
    setting_changes = _setting_changes(session)
    active_owner_sets = _active_owner_sets(session)

    rows: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    previous_season: Season | None = None
    for season in seasons:
        reg_weeks = season.regular_season_weeks
        playoff_weeks = season.playoff_weeks
        league_size = sizes.get(int(season.season_id), 0)
        raw_league_size = raw_sizes.get(int(season.season_id), league_size)
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
        details.extend(_scoring_rule_changes(season, previous_season, scoring_rules))
        details.extend(_roster_changes(season, previous_season, roster_sigs))
        details.extend(setting_changes.get(int(season.year), []))
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
        details = _resolve_setting_gaps(details, previous_season)
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
            "is_scored": int(season.season_id) in scored_ids,
            "schedule_source": "scraped"
            if reg_weeks is not None or playoff_weeks is not None
            else "unavailable",
            **source,
            "changes": changes,
        }
        rows.append(row)
        previous = row
        previous_season = season

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


def _era_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["league_size"],
        row["regular_season_weeks"],
        row["playoff_weeks"],
        row["scoring_provenance"],
        row["is_scored"],
    )


def _era_label(row: dict[str, Any]) -> str:
    bits = [f"{row['league_size']}-team league"]
    if row["regular_season_weeks"]:
        bits.append(f"{row['regular_season_weeks']}-week regular season")
    if row["is_scored"]:
        bits.append("reconstructed player-scoring era")
    else:
        bits.append("team-total-only era")
    return " / ".join(bits)


def league_eras(session: Session) -> dict[str, Any]:
    """Material era changes derived from what the dashboard can prove today."""
    timeline = league_timeline(session)
    seasons = timeline["seasons"]
    eras: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    previous_key: tuple[Any, ...] | None = None

    for row in seasons:
        key = _era_key(row)
        if current is None or key != previous_key:
            current = {
                "era_id": f"era-{len(eras) + 1}",
                "label": _era_label(row),
                "start_year": row["season_year"],
                "end_year": row["season_year"],
                "season_years": [row["season_year"]],
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
        else:
            current["end_year"] = row["season_year"]
            current["season_years"].append(row["season_year"])
        previous_key = key

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
