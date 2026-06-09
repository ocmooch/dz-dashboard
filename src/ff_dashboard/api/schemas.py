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


class StandingsInsightTeam(BaseModel):
    team_id: int
    owner_id: int
    owner_name: str | None = None
    team_name: str | None = None
    actual_wins: float
    all_play_win_pct: float
    expected_wins: float
    luck_delta: float
    points_for_rank: int
    standings_rank: int


class StandingsInsights(BaseModel):
    season_id: int
    season_year: int
    through_week: int
    available: bool
    reason: str | None = None
    teams: list[StandingsInsightTeam]


class BracketTeam(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_id: int | None = None
    owner_name: str | None = None
    score: float | None = None
    is_winner: bool = False


class BracketGame(BaseModel):
    matchup_id: int
    is_playoff: bool = False
    is_consolation: bool | None = None
    team_a: BracketTeam | None = None
    team_b: BracketTeam | None = None
    winner_team_id: int | None = None


class BracketWeek(BaseModel):
    week: int
    games: list[BracketGame]


class SeasonBracket(BaseModel):
    season_id: int
    season_year: int
    regular_season_weeks: int
    available: bool
    reason: str | None = None
    caveat: str
    weeks: list[BracketWeek]


# ---------------------------------------------------------------------------
# League history, rules/eras, and stories
# ---------------------------------------------------------------------------


class DataCaveat(BaseModel):
    code: str
    label: str
    scope: str


class LeagueInfo(BaseModel):
    league_id: str
    name: str
    platform: str | None = None
    start_year: int | None = None
    current_year: int | None = None
    season_count: int


class LeagueChangeDetail(BaseModel):
    category: str
    title: str
    summary: str
    before: str | None = None
    after: str | None = None
    source: str
    certainty: str


class SeasonChangeFlags(BaseModel):
    league_size_changed: bool = False
    schedule_changed: bool = False
    scoring_availability_changed: bool = False
    details: list[LeagueChangeDetail] = []


class LeagueTimelineSeason(BaseModel):
    season_id: int
    season_year: int
    status: str | None = None
    league_size: int
    regular_season_weeks: int | None = None
    playoff_weeks: int | None = None
    championship_week: int | None = None
    champion: TeamRef | None = None
    runner_up: TeamRef | None = None
    last_place: TeamRef | None = None
    is_scored: bool
    schedule_source: str
    scoring_provenance: str
    verification_status: str
    source: str
    changes: SeasonChangeFlags


class LeagueOverview(BaseModel):
    league_id: str
    name: str
    platform: str | None = None
    start_year: int | None = None
    current_year: int | None = None
    season_count: int
    league_size_min: int | None = None
    league_size_max: int | None = None
    completed_seasons: int
    scored_seasons: int
    champions_recorded: int
    current_era: dict[str, Any] | None = None
    data_caveats: list[DataCaveat]


class LeagueTimeline(BaseModel):
    league: LeagueInfo
    seasons: list[LeagueTimelineSeason]


class LeagueEra(BaseModel):
    era_id: str
    label: str
    start_year: int
    end_year: int
    season_years: list[int]
    league_size: int
    regular_season_weeks: int | None = None
    playoff_weeks: int | None = None
    scoring_provenance: str
    verification_status: str
    certainty: str


class LeagueEraChange(BaseModel):
    season_year: int
    league_size_changed: bool = False
    schedule_changed: bool = False
    scoring_availability_changed: bool = False
    details: list[LeagueChangeDetail] = []


class LeagueEras(BaseModel):
    league: LeagueInfo
    eras: list[LeagueEra]
    changes: list[LeagueEraChange]


class ManagerIdentity(BaseModel):
    manager_id: int
    display_name: str | None = None
    human_name: str | None = None
    aliases: list[str] = []
    nfl_user_id: str | None = None
    active_years: list[int]
    joined_year: int | None = None
    left_year: int | None = None
    is_active: bool
    team_names: list[str]
    seasons_managed: int
    identity_source: str


class ManagerDirectory(BaseModel):
    managers: list[ManagerIdentity]


class StoryCard(BaseModel):
    model_config = ConfigDict(extra="allow")

    story_id: str
    title: str
    available: bool
    reason: str | None = None
    season_year: int | None = None
    week: int | None = None
    matchup_id: int | None = None
    metric_label: str
    metric_value: float | int | None = None
    primary_team: TeamRef | None = None
    secondary_team: TeamRef | None = None
    primary_owner: OwnerRef | None = None
    caveat: str | None = None


class LeagueStories(BaseModel):
    stories: list[StoryCard]


# ---------------------------------------------------------------------------
# Owners
# ---------------------------------------------------------------------------


class TrophyEntry(BaseModel):
    season_year: int | None = None
    team_name: str | None = None
    finish: int | None = None
    is_champion: bool


class OwnerConsistency(BaseModel):
    available: bool
    reason: str | None = None
    weekly_points_stdev: float | None = None
    rank_among_owners: int | None = None
    best_season_year: int | None = None
    best_season_points_for: float | None = None
    signature: str | None = None


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
    consistency: OwnerConsistency | None = None


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
    # Derived finish label: "Champion" / "Runner-up" / "3rd place" / "Nth".
    # null (a gap, never 0) for an in-progress or rank-less season.
    result: str | None = None
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
# Power ranking
# ---------------------------------------------------------------------------


class PowerRow(BaseModel):
    rank: int
    team_id: int
    team_name: str | None = None
    owner_id: int
    owner_name: str | None = None
    wins: int
    losses: int
    ties: int
    points_for: float
    power_score: float
    points_for_per_game: float
    all_play_win_pct: float
    win_pct: float
    recent_points_for_per_game: float
    z_points_for: float
    z_all_play_win_pct: float
    z_win_pct: float
    z_recent: float
    standings_rank: int
    rank_delta: int  # standings_rank - power_rank; >0 = model rates above record


class PowerRanking(BaseModel):
    season_id: int
    season_year: int
    through_week: int
    regular_season_weeks: int
    weights: dict[str, float]
    explainer: str
    rows: list[PowerRow]


class PowerTimelinePoint(BaseModel):
    week: int
    rank: int
    power_score: float


class PowerTimelineTeam(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_id: int
    owner_name: str | None = None
    points: list[PowerTimelinePoint]


class PowerTimeline(BaseModel):
    season_id: int
    season_year: int
    regular_season_weeks: int
    teams: list[PowerTimelineTeam]


# ---------------------------------------------------------------------------
# Head-to-head & rivalries
# ---------------------------------------------------------------------------


class H2HMeeting(BaseModel):
    """A single oriented meeting reference (deep-linkable via ``matchup_id``)."""

    season_year: int | None = None
    week: int | None = None
    matchup_id: int | None = None
    margin_for_a: float | None = None


class HeadToHead(BaseModel):
    model_config = ConfigDict(extra="allow")

    owner_a: OwnerRef
    owner_b: OwnerRef
    available: bool
    games_played: int
    reason: str | None = None
    # Signed aggregate margin across all meetings (null on the no-meetings gap).
    cumulative_margin_for_a: float | None = None
    # The nearest meeting (smallest |margin|), oriented to A. The lopsided and
    # highest-scoring meetings remain extra fields on the payload.
    closest_meeting: H2HMeeting | None = None


class RivalryCell(BaseModel):
    a: int
    b: int
    games: int
    a_win_pct: float | None = None


class RivalryOwner(OwnerRef):
    # Drives the "show inactive managers" toggle on the rivalry grid: managers
    # who have left the league default to hidden so the matrix stays readable.
    is_active: bool = True


class RivalryMatrix(BaseModel):
    owners: list[RivalryOwner]
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
# Draft
# ---------------------------------------------------------------------------


class DraftPick(BaseModel):
    overall: int
    round: int
    pick_in_round: int
    team_id: int
    team_name: str | None = None
    owner_id: int | None = None
    owner_name: str | None = None
    player_id: int
    player_name: str | None = None
    position: str | None = None
    season_year: int | None = None
    season_points: float | None = None  # null (not 0) when the player has no scored rows
    value: float | None = None  # season_points - expected-at-slot; null when uncomputable
    available: bool = True
    reason: str | None = None


class DraftRound(BaseModel):
    round: int
    picks: list[DraftPick]


class DraftBoard(BaseModel):
    season_id: int
    season_year: int
    available: bool
    reason: str | None = None
    num_teams: int | None = None
    rounds: list[DraftRound]


class DraftValue(BaseModel):
    season_id: int
    season_year: int
    available: bool
    reason: str | None = None
    definition: str
    slot_window: int
    picks: list[DraftPick]
    steals: list[DraftPick]
    busts: list[DraftPick]


class DraftRecords(BaseModel):
    available: bool
    reason: str | None = None
    definition: str
    best_picks: list[DraftPick]
    worst_picks: list[DraftPick]


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


class PlayerIndexRow(BaseModel):
    """One row of the player index, enriched so relevance is legible without the
    SPA doing any joins. Public index rows are always league-relevant, so
    ``first/last_rostered_season`` should be present for normal data."""

    player_id: int
    name_full: str
    position: str | None = None
    nfl_team: str | None = None
    first_rostered_season: int | None = None
    last_rostered_season: int | None = None


class PlayerIndex(BaseModel):
    players: list[PlayerIndexRow]
    limit: int
    offset: int


class ScoringWeek(BaseModel):
    week: int
    points: float | None = None
    breakdown: dict[str, Any] = {}
    zero_reason: str | None = None
    zero_detail: str | None = None


class PlayerScoring(BaseModel):
    player_id: int
    season_year: int
    available: bool
    total_points: float | None = None
    reason: str | None = None
    weeks: list[ScoringWeek]


class OwnershipSpan(BaseModel):
    """A contiguous tenure on one team within a season — consecutive weekly
    roster rows collapsed so a season-long hold reads as one span, not ~17."""

    team_id: int
    team_name: str | None = None
    owner_id: int
    owner_name: str | None = None
    season_year: int
    week_start: int
    week_end: int
    weeks: int
    acquisition_type: str | None = None


class PlayerOwnership(BaseModel):
    player_id: int
    first_rostered_season: int | None = None
    last_rostered_season: int | None = None
    events: list[OwnershipSpan]


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


class PlayerInsightWeek(BaseModel):
    season_year: int
    week: int
    points: float


class PlayerInsightSeason(BaseModel):
    season_year: int
    points: float


class PlayerRosterSpan(BaseModel):
    first_rostered_season: int | None = None
    last_rostered_season: int | None = None


class PlayerInsightOwner(BaseModel):
    owner_id: int
    display_name: str | None = None
    weeks: int


class PlayerInsights(BaseModel):
    player_id: int
    available: bool
    reason: str | None = None
    best_week: PlayerInsightWeek | None = None
    best_season: PlayerInsightSeason | None = None
    league_roster_span: PlayerRosterSpan
    most_rostered_by: PlayerInsightOwner | None = None


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


class EnteringRecord(BaseModel):
    """A team's regular-season W-L-T entering a given week of the season."""

    wins: int = 0
    losses: int = 0
    ties: int = 0


class GameTeam(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_name: str | None = None
    score: float | None = None
    is_winner: bool = False
    entering_record: EnteringRecord | None = None


class GameCard(BaseModel):
    """One game, folded back from Phase 1's two perspective rows. ``matchup_id``
    deep-links to the box score. ``is_close`` / ``is_blowout`` are backend
    margin flags (thresholds in ``analytics/matchups.py``); both False when the
    game has no scores yet."""

    matchup_id: int
    is_playoff: bool = False
    team_a: GameTeam | None = None
    team_b: GameTeam | None = None
    margin: float | None = None
    is_close: bool = False
    is_blowout: bool = False
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
    projection_delta: float | None = None
    team_point_share: float | None = None
    lineup_value: str | None = None
    available: bool = True
    reason: str | None = None
    # Context for a *0.0* league result (null otherwise). "bye" / "did_not_play"
    # are status reasons (the player did not play); a plain played-and-scored-0
    # carries no reason; "unexpected" flags a 0 that does not cleanly fit, with an
    # attempted explanation in ``zero_detail``.
    zero_reason: str | None = None  # "bye" | "did_not_play" | "unexpected" | null
    zero_detail: str | None = None  # human-readable note, mainly for "unexpected"


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


# ---------------------------------------------------------------------------
# Team page
# ---------------------------------------------------------------------------


class TeamOverview(BaseModel):
    team_id: int
    team_name: str | None = None
    season_id: int
    season_year: int
    owner_id: int
    owner_name: str | None = None
    rank: int | None = None
    rank_basis: str  # "final_rank" | "computed"
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    final_rank: int | None = None
    made_playoffs: bool | None = None
    is_champion: bool
    is_scored: bool


class TeamRosterPlayer(BaseModel):
    player_id: int
    player_name: str | None = None
    position: str | None = None
    nfl_team: str | None = None
    roster_slot: str | None = None
    is_starter: bool
    league_points: float | None = None  # null (not 0) for unscored slots/seasons
    acquisition_type: str | None = None
    acquisition_week: int | None = None


class TeamRosterOut(BaseModel):
    team_id: int
    season_year: int
    week: int
    weeks_available: list[int]
    is_scored: bool
    players: list[TeamRosterPlayer]


class ScheduleGame(BaseModel):
    matchup_id: int
    week: int
    is_playoff: bool = False
    opponent_team_id: int | None = None
    opponent_team_name: str | None = None
    opponent_owner_name: str | None = None
    team_score: float | None = None
    opponent_score: float | None = None
    result: str | None = None  # W / L / T
    margin: float | None = None


class TeamSchedule(BaseModel):
    team_id: int
    season_year: int
    games: list[ScheduleGame]


class ScoringTrendPoint(BaseModel):
    week: int
    team_score: float | None = None
    league_avg: float | None = None
    is_playoff: bool = False


class TeamScoringTrend(BaseModel):
    team_id: int
    season_year: int
    is_scored: bool
    points: list[ScoringTrendPoint]


class TeamTransaction(BaseModel):
    transaction_id: int
    transaction_type: str
    executed_at: str | None = None
    effective_week: int | None = None
    player_id: int | None = None
    player_name: str | None = None
    direction: str | None = None
    waiver_priority_used: int | None = None
    faab_bid: float | None = None
    counterpart_team_id: int | None = None
    counterpart_team_name: str | None = None
    notes: str | None = None
    extra_data: dict[str, Any] | None = None


class TeamTransactions(BaseModel):
    team_id: int
    season_year: int
    transactions: list[TeamTransaction]


class RosterMove(BaseModel):
    week: int
    player_id: int
    player_name: str | None = None
    position: str | None = None
    action: str  # "add" | "drop" | "retain"


class TeamRosterMoves(BaseModel):
    team_id: int
    season_year: int
    is_scored: bool  # informational; moves are NOT gated on it
    available: bool  # False when <2 distinct roster snapshot weeks
    roster_weeks: list[int]
    moves: list[RosterMove]


# ---------------------------------------------------------------------------
# Global search (typeahead across owners, seasons, and players)
# ---------------------------------------------------------------------------


class SearchHit(BaseModel):
    type: str  # "owner" | "season" | "player"
    id: int
    label: str
    sublabel: str | None = None
    href: str


class SearchResults(BaseModel):
    query: str
    hits: list[SearchHit]
