"""Pydantic response models for the dashboard analytics API.

The success envelope, ``Meta``, and ``ErrorBody`` are reused verbatim from
Phase 1 (``ff_pipeline.api.schemas``) so the dashboard's contract is identical
to the read API — one source of truth, no copy-drift. Everything below is
analytics-specific and additive.
"""

from __future__ import annotations

from typing import Any

from ff_pipeline.api.schemas import (
    Envelope,
    ErrorBody,
    HealthResponse,
    Meta,
    PlayerLite,
    PlayerOut,
    SeasonTotal,
    TopScorer,
)
from pydantic import BaseModel, ConfigDict

__all__ = [
    "Coverage",
    "Envelope",
    "ErrorBody",
    "HealthResponse",
    "LatestRun",
    "Meta",
    "MetaResponse",
    "PlayerLite",
    "PlayerOut",
    "SeasonTotal",
    "TopScorer",
]


# ---------------------------------------------------------------------------
# Meta / coverage (powers the "data as of" indicator + gap banners)
# ---------------------------------------------------------------------------


class LatestRun(BaseModel):
    run_id: int | None = None
    status: str | None = None
    mode: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class Coverage(BaseModel):
    """What in the database is trustworthy, partial, or absent.

    Mirrors the reliability map in ``docs/03_DATA_ACCESS.md`` so the frontend
    can render honest gap affordances rather than fabricated zeros.
    """

    seasons_present: list[int]
    seasons_scored: list[int]
    scored_year_min: int | None = None
    scored_year_max: int | None = None
    reconstruction_complete: bool
    availability_current_season_only: bool = True
    dst_scoring_complete: bool = False


class MetaResponse(BaseModel):
    latest_run: LatestRun
    coverage: Coverage


# ---------------------------------------------------------------------------
# Shared references
# ---------------------------------------------------------------------------


class TeamRef(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_id: int | None = None
    owner_name: str | None = None


class OwnerRef(BaseModel):
    owner_id: int
    display_name: str | None = None


# ---------------------------------------------------------------------------
# Seasons & standings
# ---------------------------------------------------------------------------


class SeasonListItem(BaseModel):
    season_id: int
    season_year: int
    status: str | None = None
    is_scored: bool
    champion: TeamRef | None = None


class SeasonList(BaseModel):
    seasons: list[SeasonListItem]


class SeasonSummary(BaseModel):
    season_id: int
    season_year: int
    status: str | None = None
    regular_season_weeks: int | None = None
    playoff_weeks: int | None = None
    champion: TeamRef | None = None
    runner_up: TeamRef | None = None
    last_place: TeamRef | None = None


class Streak(BaseModel):
    result: str | None = None
    length: int = 0


class StandingRow(BaseModel):
    rank: int
    team_id: int
    team_name: str | None = None
    owner_id: int
    owner_name: str | None = None
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    win_pct: float
    streak: Streak
    final_rank: int | None = None


class Standings(BaseModel):
    season_id: int
    season_year: int
    through_week: int
    regular_season_weeks: int
    rank_basis: str  # "final_rank" | "computed"
    tiebreak_caveat: bool
    rows: list[StandingRow]


class TimelinePoint(BaseModel):
    week: int
    rank: int
    points_for: float


class TimelineTeam(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_id: int
    owner_name: str | None = None
    points: list[TimelinePoint]


class StandingsTimeline(BaseModel):
    season_id: int
    season_year: int
    regular_season_weeks: int
    teams: list[TimelineTeam]


# ---------------------------------------------------------------------------
# Owners
# ---------------------------------------------------------------------------


class TrophyEntry(BaseModel):
    season_year: int | None = None
    team_name: str | None = None
    finish: int | None = None
    is_champion: bool


class OwnerCareer(BaseModel):
    owner_id: int
    display_name: str | None = None
    seasons_played: int
    total_wins: int
    total_losses: int
    total_ties: int
    total_points_for: float
    championships: int
    best_finish: int | None = None
    avg_finish: float | None = None
    trophy_case: list[TrophyEntry] = []


class OwnersList(BaseModel):
    owners: list[OwnerCareer]


class OwnerSeasonRow(BaseModel):
    season_id: int
    season_year: int | None = None
    team_id: int
    team_name: str | None = None
    wins: int
    losses: int
    ties: int
    points_for: float
    final_rank: int | None = None
    made_playoffs: bool | None = None
    is_champion: bool


class OwnerSeasons(BaseModel):
    owner_id: int
    display_name: str | None = None
    seasons: list[OwnerSeasonRow]


class TrajectoryPoint(BaseModel):
    season_year: int | None = None
    final_rank: int | None = None
    points_for: float


class OwnerTrajectory(BaseModel):
    owner_id: int
    display_name: str | None = None
    points: list[TrajectoryPoint]


# ---------------------------------------------------------------------------
# Head-to-head & rivalries
# ---------------------------------------------------------------------------


class HeadToHead(BaseModel):
    model_config = ConfigDict(extra="allow")

    owner_a: OwnerRef
    owner_b: OwnerRef
    available: bool
    games_played: int
    reason: str | None = None


class RivalryCell(BaseModel):
    a: int
    b: int
    games: int
    a_win_pct: float | None = None


class RivalryMatrix(BaseModel):
    owners: list[OwnerRef]
    cells: list[RivalryCell]


# ---------------------------------------------------------------------------
# Records book
# ---------------------------------------------------------------------------


class RecordsBook(BaseModel):
    """Heterogeneous superlatives; each value is an availability-tagged object.

    Kept extra-permissive so each record can carry its own context fields
    (matchup_id, player_id, owner_name, …) for deep-linking without a model per
    record. The frontend reads ``available`` first, then the value/context.
    """

    model_config = ConfigDict(extra="allow")

    scored_era: list[int]


class ChampionshipEntry(BaseModel):
    season_year: int
    champion: TeamRef | None = None
    runner_up: TeamRef | None = None
    last_place: TeamRef | None = None


class ChampionshipHistory(BaseModel):
    seasons: list[ChampionshipEntry]


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


class PlayerIndex(BaseModel):
    players: list[PlayerLite]
    limit: int
    offset: int


class ScoringWeek(BaseModel):
    week: int
    points: float | None = None
    breakdown: dict[str, Any] = {}


class PlayerScoring(BaseModel):
    player_id: int
    season_year: int
    available: bool
    total_points: float | None = None
    reason: str | None = None
    weeks: list[ScoringWeek]


class OwnershipEvent(BaseModel):
    team_id: int
    team_name: str | None = None
    season_year: int
    week: int
    roster_slot: str | None = None
    acquisition_type: str | None = None


class PlayerOwnership(BaseModel):
    player_id: int
    events: list[OwnershipEvent]


class AvailabilityWeek(BaseModel):
    week: int
    status: str
    owning_team_id: int | None = None
    is_pre_kickoff_snapshot: bool


class PlayerAvailability(BaseModel):
    player_id: int
    season_year: int
    available: bool
    reason: str | None = None
    weeks: list[AvailabilityWeek]


class TopScorers(BaseModel):
    season_year: int
    week: int | None = None
    position: str | None = None
    scorers: list[TopScorer]


class SeasonTotals(BaseModel):
    season_year: int
    position: str | None = None
    totals: list[SeasonTotal]


# ---------------------------------------------------------------------------
# Matchups & box scores
# ---------------------------------------------------------------------------


class GameTeam(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_name: str | None = None
    score: float | None = None
    is_winner: bool = False


class GameCard(BaseModel):
    """One game, folded back from Phase 1's two perspective rows. ``matchup_id``
    deep-links to the box score."""

    matchup_id: int
    is_playoff: bool = False
    team_a: GameTeam | None = None
    team_b: GameTeam | None = None
    margin: float | None = None
    winner_team_id: int | None = None


class WeekMatchups(BaseModel):
    season_id: int
    season_year: int
    week: int
    is_scored: bool
    games: list[GameCard]


class BoxPlayer(BaseModel):
    roster_slot: str | None = None
    player_id: int
    player_name: str | None = None
    position: str | None = None
    league_points: float | None = None  # null (not 0) when unscored — see ``reason``
    is_starter: bool
    breakdown: dict[str, Any] = {}
    projection: float | None = None
    available: bool = True
    reason: str | None = None


class BoxTeam(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_name: str | None = None
    total_score: float | None = None  # authoritative team total from Phase 1
    starter_points: float  # sum of scored starters (drives points-left)
    bench_points: float
    optimal_total: float
    points_left_on_bench: float
    beat_projection_by: float | None = None
    lineup: list[BoxPlayer]


class BoxScore(BaseModel):
    matchup_id: int
    season_year: int | None = None
    week: int
    available: bool
    reason: str | None = None
    is_playoff: bool = False
    home: BoxTeam | None = None
    away: BoxTeam | None = None
    winner_team_id: int | None = None
