"""Reviewed artifact and weekly historical-division analytics."""

from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from ff_pipeline.repository.models import Team
from sqlalchemy import select

from ff_dashboard.analytics import conferences
from ff_dashboard.analytics.conferences import season_conferences
from ff_dashboard.analytics.historical_divisions import (
    ARTIFACT_PATH,
    HistoricalDivision,
    HistoricalDivisionSeason,
    HistoricalDivisionTeam,
    historical_division_seasons,
    validate_artifact,
)
from ff_dashboard.analytics.standings import compute_standings
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _payload() -> dict:
    with ARTIFACT_PATH.open(encoding="utf-8") as artifact:
        return json.load(artifact)


def test_artifact_pins_all_historical_seasons_and_teams() -> None:
    assert sha256(ARTIFACT_PATH.read_bytes()).hexdigest() == (
        "a70b564a00f838711f7e2a4df697e3010b304a3b38eb45aff002e74ad85c40b4"
    )
    seasons = historical_division_seasons()
    assert set(seasons) == set(range(2010, 2020))
    assert (
        sum(len(division.teams) for season in seasons.values() for division in season.divisions)
        == 120
    )
    assert [len(division.teams) for division in seasons[2010].divisions] == [4, 4, 4]
    assert [division.name for division in seasons[2010].divisions] == [None, None, None]
    assert [len(division.teams) for division in seasons[2018].divisions] == [6, 6]
    assert [division.name for division in seasons[2018].divisions] == ["Westeros", "Essos"]


def test_artifact_source_ranks_are_complete_and_unique() -> None:
    for season in historical_division_seasons().values():
        teams = [team for division in season.divisions for team in division.teams]
        assert sorted(team.final_overall_regular_season_rank for team in teams) == list(
            range(1, 13)
        )
        assert sorted(team.nfl_team_id for team in teams) == list(range(1, 13))
        for division in season.divisions:
            assert [team.final_division_rank for team in division.teams] == list(
                range(1, len(division.teams) + 1)
            )


def test_artifact_validation_rejects_duplicate_assignment() -> None:
    payload = deepcopy(_payload())
    payload["seasons"][0]["divisions"][1]["teams"][0]["nfl_team_id"] = 6
    with pytest.raises(ValueError, match="appears twice"):
        validate_artifact(payload)


def test_artifact_validation_rejects_rank_gap() -> None:
    payload = deepcopy(_payload())
    payload["seasons"][8]["divisions"][0]["teams"][0]["final_overall_regular_season_rank"] = 12
    with pytest.raises(ValueError, match="overall ranks"):
        validate_artifact(payload)


def _fixture_source() -> HistoricalDivisionSeason:
    return HistoricalDivisionSeason(
        season=2016,
        source_url="https://example.invalid/regular",
        captured_at="2026-06-17",
        divisions=(
            HistoricalDivision(
                division_number=1,
                name="Alpha",
                teams=(
                    HistoricalDivisionTeam(1, 1, 1),
                    HistoricalDivisionTeam(2, 2, 4),
                ),
            ),
            HistoricalDivision(
                division_number=2,
                name="Beta",
                teams=(
                    HistoricalDivisionTeam(3, 1, 2),
                    HistoricalDivisionTeam(4, 2, 3),
                ),
            ),
        ),
    )


class _Rows:
    def __init__(self, rows: list[tuple[int, str | None]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[int, str | None]]:
        return self.rows


class _MappingSession:
    def __init__(self, rows: list[tuple[int, str | None]]) -> None:
        self.rows = rows

    def execute(self, _query: object) -> _Rows:
        return _Rows(self.rows)


def test_mapping_audit_reports_missing_duplicate_and_extra_source_ids() -> None:
    source = _fixture_source()
    session = _MappingSession([(101, "1"), (102, "1"), (103, "2"), (104, "9")])
    mapping, issues = conferences._map_source_teams(session, 1, source)  # type: ignore[arg-type]
    assert mapping == {2: 103}
    assert "source_team_duplicated_in_db:1" in issues
    assert "source_team_missing_from_db:3" in issues
    assert "source_team_missing_from_db:4" in issues
    assert "db_team_missing_from_source:9" in issues


def test_mapping_audit_reports_source_team_in_multiple_divisions() -> None:
    source = _fixture_source()
    duplicate = HistoricalDivisionSeason(
        season=source.season,
        source_url=source.source_url,
        captured_at=source.captured_at,
        divisions=(
            source.divisions[0],
            HistoricalDivision(
                division_number=2,
                name="Beta",
                teams=(
                    HistoricalDivisionTeam(1, 1, 2),
                    HistoricalDivisionTeam(4, 2, 3),
                ),
            ),
        ),
    )
    session = _MappingSession([(101, "1"), (102, "2"), (103, "3"), (104, "4")])
    _, issues = conferences._map_source_teams(session, 1, duplicate)  # type: ignore[arg-type]
    assert "source_team_in_multiple_divisions:1" in issues


def _fixture_mapping(session: Session) -> dict[int, int]:
    rows = session.execute(
        select(Team.team_id, Team.owner_id).where(Team.season_id == KNOWN["season_id"][2016])
    ).all()
    owner_to_team = {int(owner_id): int(team_id) for team_id, owner_id in rows}
    return {
        1: owner_to_team[KNOWN["owner_id"]["mav"]],
        2: owner_to_team[KNOWN["owner_id"]["ice"]],
        3: owner_to_team[KNOWN["owner_id"]["goose"]],
        4: owner_to_team[KNOWN["owner_id"]["slider"]],
    }


def test_weekly_division_records_and_midseason_order(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _fixture_source()
    mapping = _fixture_mapping(session)
    monkeypatch.setattr(conferences, "_mapped_source", lambda *_: (source, mapping, []))

    data = season_conferences(session, KNOWN["season_id"][2016], through_week=1)
    assert data is not None and data["available"] is True
    assert data["through_week"] == 1
    alpha, beta = data["conferences"]
    assert [team["owner_name"] for team in alpha["teams"]] == ["Maverick", "Iceman"]
    assert [team["conference_rank"] for team in alpha["teams"]] == [1, 2]
    assert [team["overall_rank"] for team in alpha["teams"]] == [1, 4]
    assert [
        (team["division_wins"], team["division_losses"], team["division_ties"])
        for team in alpha["teams"]
    ] == [(1, 0, 0), (0, 1, 0)]
    assert [team["owner_name"] for team in beta["teams"]] == ["Goose", "Slider"]
    overall = compute_standings(session, KNOWN["season_id"][2016], through_week=1)
    assert overall is not None
    by_team = {team["team_id"]: team for team in overall["rows"]}
    for division in data["conferences"]:
        for team in division["teams"]:
            expected = by_team[team["team_id"]]
            assert (team["points_for"], team["points_against"], team["streak"]) == (
                expected["points_for"],
                expected["points_against"],
                expected["streak"],
            )


def test_final_view_uses_source_division_and_overall_ranks(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _fixture_source()
    mapping = _fixture_mapping(session)
    monkeypatch.setattr(conferences, "_mapped_source", lambda *_: (source, mapping, []))

    data = season_conferences(session, KNOWN["season_id"][2016])
    assert data is not None and data["available"] is True
    by_owner = {
        team["owner_name"]: team for division in data["conferences"] for team in division["teams"]
    }
    assert (by_owner["Maverick"]["conference_rank"], by_owner["Maverick"]["overall_rank"]) == (1, 1)
    assert (by_owner["Iceman"]["conference_rank"], by_owner["Iceman"]["overall_rank"]) == (2, 4)
    assert (by_owner["Goose"]["conference_rank"], by_owner["Goose"]["overall_rank"]) == (1, 2)
    assert (by_owner["Slider"]["conference_rank"], by_owner["Slider"]["overall_rank"]) == (2, 3)
    # Week 2 games are cross-division, so the exact week-1 division records remain.
    assert (by_owner["Maverick"]["division_wins"], by_owner["Maverick"]["division_losses"]) == (
        1,
        0,
    )


def test_mapping_gap_is_returned_without_partial_tables(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _fixture_source()
    monkeypatch.setattr(
        conferences,
        "_mapped_source",
        lambda *_: (source, {}, ["source_team_missing_from_db:1"]),
    )
    data = season_conferences(session, KNOWN["season_id"][2016])
    assert data is not None
    assert data["available"] is False
    assert data["reason"] == "historical_division_mapping_gap"
    assert data["conferences"] == []
    assert "source_team_missing_from_db:1" in data["mapping_issues"]


def test_2020_has_no_division_grouping(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        conferences,
        "get_season",
        lambda *_: SimpleNamespace(year=2020),
    )
    monkeypatch.setattr(
        conferences,
        "compute_standings",
        lambda *_args, **_kwargs: {"through_week": 13, "regular_season_weeks": 13, "rows": []},
    )
    data = season_conferences(session, 999)
    assert data is not None
    assert data["available"] is False
    assert data["reason"] == "no_conferences_this_season"
    assert data["conferences"] == []
