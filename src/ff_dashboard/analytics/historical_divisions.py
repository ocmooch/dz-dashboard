"""Reviewed NFL.com regular-season division membership and source ranks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

ARTIFACT_PATH = Path(__file__).resolve().parents[1] / "data" / "historical_divisions.json"
HISTORICAL_YEARS = frozenset(range(2010, 2020))


@dataclass(frozen=True)
class HistoricalDivisionTeam:
    nfl_team_id: int
    final_division_rank: int
    final_overall_regular_season_rank: int


@dataclass(frozen=True)
class HistoricalDivision:
    division_number: int
    name: str | None
    teams: tuple[HistoricalDivisionTeam, ...]


@dataclass(frozen=True)
class HistoricalDivisionSeason:
    season: int
    source_url: str
    captured_at: str
    divisions: tuple[HistoricalDivision, ...]


def _contiguous(values: list[int]) -> bool:
    return sorted(values) == list(range(1, len(values) + 1))


def validate_artifact(payload: dict[str, Any]) -> dict[int, HistoricalDivisionSeason]:
    """Validate and normalize the committed artifact, raising ``ValueError`` on drift."""
    if payload.get("schema_version") != 1:
        raise ValueError("historical divisions: unsupported schema_version")
    raw_seasons = payload.get("seasons")
    if not isinstance(raw_seasons, list):
        raise ValueError("historical divisions: seasons must be a list")

    seasons: dict[int, HistoricalDivisionSeason] = {}
    for raw_season in raw_seasons:
        year = int(raw_season["season"])
        if year in seasons:
            raise ValueError(f"historical divisions: duplicate season {year}")
        raw_divisions = raw_season["divisions"]
        division_numbers = [int(d["division_number"]) for d in raw_divisions]
        if not _contiguous(division_numbers):
            raise ValueError(f"historical divisions: non-contiguous divisions for {year}")

        seen_team_ids: set[int] = set()
        overall_ranks: list[int] = []
        divisions: list[HistoricalDivision] = []
        for raw_division in raw_divisions:
            teams = tuple(
                HistoricalDivisionTeam(
                    nfl_team_id=int(team["nfl_team_id"]),
                    final_division_rank=int(team["final_division_rank"]),
                    final_overall_regular_season_rank=int(
                        team["final_overall_regular_season_rank"]
                    ),
                )
                for team in raw_division["teams"]
            )
            division_ranks = [team.final_division_rank for team in teams]
            if not _contiguous(division_ranks):
                raise ValueError(
                    f"historical divisions: non-contiguous division ranks for "
                    f"{year} division {raw_division['division_number']}"
                )
            for team in teams:
                if team.nfl_team_id in seen_team_ids:
                    raise ValueError(
                        f"historical divisions: team {team.nfl_team_id} appears twice in {year}"
                    )
                seen_team_ids.add(team.nfl_team_id)
                overall_ranks.append(team.final_overall_regular_season_rank)
            divisions.append(
                HistoricalDivision(
                    division_number=int(raw_division["division_number"]),
                    name=raw_division.get("name"),
                    teams=teams,
                )
            )

        if len(seen_team_ids) != 12:
            raise ValueError(f"historical divisions: {year} must contain 12 teams")
        if not _contiguous(overall_ranks):
            raise ValueError(f"historical divisions: non-contiguous overall ranks for {year}")
        if year == 2010 and [len(d.teams) for d in divisions] != [4, 4, 4]:
            raise ValueError("historical divisions: 2010 must be three divisions of four")
        if year == 2018 and (
            [len(d.teams) for d in divisions] != [6, 6] or any(not d.name for d in divisions)
        ):
            raise ValueError("historical divisions: 2018 must be two named divisions of six")

        seasons[year] = HistoricalDivisionSeason(
            season=year,
            source_url=str(raw_season["source_url"]),
            captured_at=str(raw_season["captured_at"]),
            divisions=tuple(divisions),
        )

    if set(seasons) != HISTORICAL_YEARS:
        missing = sorted(HISTORICAL_YEARS - set(seasons))
        extra = sorted(set(seasons) - HISTORICAL_YEARS)
        raise ValueError(
            f"historical divisions: year coverage mismatch missing={missing} extra={extra}"
        )
    return seasons


@lru_cache(maxsize=1)
def historical_division_seasons() -> dict[int, HistoricalDivisionSeason]:
    with ARTIFACT_PATH.open(encoding="utf-8") as artifact:
        payload: dict[str, Any] = json.load(artifact)
    return validate_artifact(payload)


def historical_division_season(year: int) -> HistoricalDivisionSeason | None:
    return historical_division_seasons().get(year)
