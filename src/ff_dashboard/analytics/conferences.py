"""BFF-owned historical division standings for the 2010-2019 league era."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository.models import Matchup, Team
from ff_pipeline.repository.queries import get_season
from sqlalchemy import select

from ff_dashboard.analytics.common import require_league
from ff_dashboard.analytics.historical_divisions import (
    HistoricalDivisionSeason,
    historical_division_season,
)
from ff_dashboard.analytics.standings import compute_standings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _map_source_teams(
    session: Session,
    season_id: int,
    source: HistoricalDivisionSeason,
) -> tuple[dict[int, int], list[str]]:
    """Return NFL.com team ID → internal team ID plus honest mapping issues."""
    db_rows = session.execute(
        select(Team.team_id, Team.team_abbrev).where(Team.season_id == season_id)
    ).all()
    by_source_id: dict[int, list[int]] = {}
    issues: list[str] = []
    for team_id_raw, abbrev_raw in db_rows:
        if abbrev_raw is None:
            issues.append(f"db_team_without_nfl_team_id:{int(team_id_raw)}")
            continue
        try:
            nfl_team_id = int(str(abbrev_raw))
        except ValueError:
            issues.append(f"db_team_invalid_nfl_team_id:{int(team_id_raw)}:{abbrev_raw}")
            continue
        by_source_id.setdefault(nfl_team_id, []).append(int(team_id_raw))

    source_ids = [team.nfl_team_id for division in source.divisions for team in division.teams]
    source_counts = Counter(source_ids)
    for nfl_team_id, count in sorted(source_counts.items()):
        if count > 1:
            issues.append(f"source_team_in_multiple_divisions:{nfl_team_id}")

    mapping: dict[int, int] = {}
    for nfl_team_id in sorted(source_counts):
        matches = by_source_id.get(nfl_team_id, [])
        if not matches:
            issues.append(f"source_team_missing_from_db:{nfl_team_id}")
        elif len(matches) > 1:
            issues.append(f"source_team_duplicated_in_db:{nfl_team_id}")
        else:
            mapping[nfl_team_id] = matches[0]

    extra_source_ids = sorted(set(by_source_id) - set(source_counts))
    for nfl_team_id in extra_source_ids:
        issues.append(f"db_team_missing_from_source:{nfl_team_id}")
    if len(set(mapping.values())) != len(mapping):
        issues.append("internal_team_mapped_multiple_times")
    return mapping, issues


def _mapped_source(
    session: Session, season_id: int, year: int
) -> tuple[HistoricalDivisionSeason | None, dict[int, int], list[str]]:
    source = historical_division_season(year)
    if source is None:
        return None, {}, []
    mapping, issues = _map_source_teams(session, season_id, source)
    return source, mapping, issues


def conference_map(session: Session, season_id: int) -> dict[int, tuple[int | None, str | None]]:
    """Return internal team → historical division ID/name, or ``{}`` on any gap."""
    season = get_season(session, season_id)
    if season is None:
        return {}
    source, mapping, issues = _mapped_source(session, season_id, season.year)
    if source is None or issues:
        return {}
    result: dict[int, tuple[int | None, str | None]] = {}
    for division in source.divisions:
        conference_id = season.year * 10 + division.division_number
        for team in division.teams:
            result[mapping[team.nfl_team_id]] = (conference_id, division.name)
    return result


def _result(matchup: Matchup) -> str | None:
    if matchup.team_score is None or matchup.opponent_score is None:
        return None
    if matchup.team_score > matchup.opponent_score:
        return "W"
    if matchup.team_score < matchup.opponent_score:
        return "L"
    return "T"


def season_conferences(
    session: Session,
    season_id: int,
    through_week: int | None = None,
) -> dict[str, Any] | None:
    """Return weekly standings grouped by the reviewed historical divisions."""
    require_league(session)
    season = get_season(session, season_id)
    if season is None:
        return None

    overall = compute_standings(session, season_id, through_week)
    if overall is None:
        return None
    base: dict[str, Any] = {
        "season_id": season_id,
        "season_year": season.year,
        "through_week": overall["through_week"],
        "regular_season_weeks": overall["regular_season_weeks"],
        "mapping_issues": [],
    }
    source, source_to_internal, issues = _mapped_source(session, season_id, season.year)
    if source is None:
        return {
            **base,
            "available": False,
            "reason": "no_conferences_this_season",
            "conferences": [],
        }

    standings_team_ids = {int(row["team_id"]) for row in overall["rows"]}
    mapped_team_ids = set(source_to_internal.values())
    for team_id in sorted(standings_team_ids - mapped_team_ids):
        issues.append(f"standings_team_missing_from_source:{team_id}")
    if issues:
        return {
            **base,
            "available": False,
            "reason": "historical_division_mapping_gap",
            "mapping_issues": sorted(set(issues)),
            "conferences": [],
        }

    team_division: dict[int, int] = {}
    source_team: dict[int, Any] = {}
    for division in source.divisions:
        for team in division.teams:
            internal_id = source_to_internal[team.nfl_team_id]
            team_division[internal_id] = division.division_number
            source_team[internal_id] = team

    division_records: dict[int, dict[str, int]] = {
        team_id: {"division_wins": 0, "division_losses": 0, "division_ties": 0}
        for team_id in standings_team_ids
    }
    matchups = session.execute(
        select(Matchup).where(
            Matchup.season_id == season_id,
            Matchup.week <= overall["through_week"],
            Matchup.is_playoff.is_(False),
        )
    ).scalars()
    for matchup in matchups:
        opponent_id = matchup.opponent_team_id
        if opponent_id is None or team_division.get(matchup.team_id) != team_division.get(
            opponent_id
        ):
            continue
        result = _result(matchup)
        if result == "W":
            division_records[matchup.team_id]["division_wins"] += 1
        elif result == "L":
            division_records[matchup.team_id]["division_losses"] += 1
        elif result == "T":
            division_records[matchup.team_id]["division_ties"] += 1

    completed = overall["through_week"] >= overall["regular_season_weeks"]
    standings_rows = {int(row["team_id"]): row for row in overall["rows"]}
    conferences_out: list[dict[str, Any]] = []
    for division in source.divisions:
        member_ids = {source_to_internal[team.nfl_team_id] for team in division.teams}
        members = [row for row in overall["rows"] if int(row["team_id"]) in member_ids]
        if completed:
            members.sort(key=lambda row: source_team[int(row["team_id"])].final_division_rank)
        teams_out: list[dict[str, Any]] = []
        for computed_division_rank, row in enumerate(members, start=1):
            team_id = int(row["team_id"])
            source_rank = source_team[team_id]
            entry = dict(standings_rows[team_id])
            entry.update(division_records[team_id])
            entry["overall_rank"] = (
                source_rank.final_overall_regular_season_rank if completed else row["rank"]
            )
            entry["conference_rank"] = (
                source_rank.final_division_rank if completed else computed_division_rank
            )
            teams_out.append(entry)
        conferences_out.append(
            {
                "conference_id": season.year * 10 + division.division_number,
                "division_number": division.division_number,
                "name": division.name,
                "teams": teams_out,
            }
        )

    return {
        **base,
        "available": True,
        "reason": None,
        "conferences": conferences_out,
    }
