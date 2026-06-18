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
    "CoverageFeedCell",
    "CoverageMatrix",
    "CoverageRelevance",
    "Envelope",
    "ErrorBody",
    "HealthResponse",
    "IdentitySplitCandidate",
    "IdentitySplitMember",
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


class IdentitySplitMember(BaseModel):
    player_id: int
    name_full: str
    position: str | None = None
    nfl_team: str | None = None
    gsis_id: str | None = None
    nfl_com_player_id: str | None = None
    rostered: bool = False
    scored: bool = False
    injured: bool = False


class IdentitySplitCandidate(BaseModel):
    name_full: str
    reason: str
    members: list[IdentitySplitMember]


class CoverageRelevance(BaseModel):
    total_players: int
    league_rostered_players: int
    league_relevant_players: int
    excluded_players: int
    identity_split_candidate_count: int
    identity_split_candidates: list[IdentitySplitCandidate]


class CoverageFeedCell(BaseModel):
    season_year: int
    week: int
    status: str
    reason: str | None = None
    row_count: int
    projected_points_count: int | None = None
    projected_stats_count: int | None = None


class CoverageMatrix(BaseModel):
    relevance: CoverageRelevance
    feeds: dict[str, list[CoverageFeedCell]]
    reason_codes: dict[str, str]


class MetaResponse(BaseModel):
    latest_run: LatestRun
    coverage: Coverage


# ---------------------------------------------------------------------------
# Commissioner history
# ---------------------------------------------------------------------------


class CommissionerTerm(BaseModel):
    owner_id: int
    owner_name: str
    from_year: int
    to_year: int | None = None
    seasons: int
    notes: str | None = None


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
    conference_id: int | None = None
    conference_name: str | None = None


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
    most_robbed: StandingsInsightTeam | None = None
    most_blessed: StandingsInsightTeam | None = None
    teams: list[StandingsInsightTeam]


class BracketTeam(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_id: int | None = None
    owner_name: str | None = None
    score: float | None = None
    is_winner: bool = False
    conference_name: str | None = None


class ByeTeam(BaseModel):
    team_id: int
    team_name: str | None = None
    owner_id: int | None = None
    owner_name: str | None = None
    conference_name: str | None = None


class BracketGame(BaseModel):
    matchup_id: int
    is_playoff: bool = False
    is_consolation: bool | None = None
    game_label: str | None = None  # "Championship", "3rd Place", "7th Place", etc.
    team_a: BracketTeam | None = None
    team_b: BracketTeam | None = None
    winner_team_id: int | None = None


class BracketRound(BaseModel):
    round_num: int
    round_label: str  # "First Round", "Semifinals", "Finals"
    bye_teams: list[ByeTeam] = []
    games: list[BracketGame]


class BracketSection(BaseModel):
    size: int
    rounds: list[BracketRound]
    bye_teams: list[ByeTeam] = []


class SeasonBracket(BaseModel):
    season_id: int
    season_year: int
    regular_season_weeks: int
    available: bool
    reason: str | None = None
    caveat: str
    consolation_distinguished: bool = False
    playoff_bracket: BracketSection | None = None
    consolation_bracket: BracketSection | None = None


# ---------------------------------------------------------------------------
# Season conferences
# ---------------------------------------------------------------------------


class ConferenceTeam(BaseModel):
    rank: int
    overall_rank: int
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
    conference_rank: int
    division_wins: int
    division_losses: int
    division_ties: int


class ConferenceSection(BaseModel):
    conference_id: int
    division_number: int
    name: str | None = None  # null for 2010's unnamed divisions
    teams: list[ConferenceTeam]


class SeasonConferences(BaseModel):
    season_id: int
    season_year: int
    through_week: int
    regular_season_weeks: int
    available: bool
    reason: str | None = None
    mapping_issues: list[str] = []
    conferences: list[ConferenceSection]


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
    changed_at: str | None = None
    participants_joined: list[str] | None = None
    participants_left: list[str] | None = None
    description_gap: bool = False
    # Tiered-classifier fields (defaulted so state-derived details stay valid).
    tier: str = "T3"  # "T1" | "T2" | "T3"
    human_label: str | None = None
    phase: str | None = None  # "in_season" | "off_season"
    event_group_key: str | None = None
    missing_context: bool = False
    members: list["LeagueChangeDetail"] = []
    canonical_type: str | None = None


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
    era_id: str
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
    commissioners: list[CommissionerTerm] = []


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
    latest_team_id: int | None = None
    trophy_case: list[TrophyEntry] = []
    consistency: OwnerConsistency | None = None
    commissioner_terms: list[CommissionerTerm] = []


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


class TeamsIndexRow(OwnerSeasonRow):
    """One team (an owner's season entry) for the Teams browser.

    The owner-season row plus owner identity, so the SPA can group the flat list
    by season or by owner without further lookups or math.
    """

    owner_id: int
    owner_name: str | None = None


class TeamsIndex(BaseModel):
    teams: list[TeamsIndexRow]


class TrajectoryPoint(BaseModel):
    season_year: int | None = None
    final_rank: int | None = None
    points_for: float


class OwnerTrajectory(BaseModel):
    owner_id: int
    display_name: str | None = None
    points: list[TrajectoryPoint]


class OwnerStory(BaseModel):
    """The "Your Story" lead band on a manager profile.

    Each superlative is its own rich, deep-linkable object (matchup_id, opponent
    ref, scores) or ``None`` when it does not clear its min-sample bar — never a
    forced 0 or fake value. The frontend reads each field and renders the line only
    when present, so the model stays extra-permissive rather than enumerating a
    class per superlative.
    """

    model_config = ConfigDict(extra="allow")

    owner: OwnerRef
    available: bool
    signature_win: dict[str, Any] | None = None
    heartbreak: dict[str, Any] | None = None
    high_water_mark: dict[str, Any] | None = None
    nemesis: dict[str, Any] | None = None
    favorite_victim: dict[str, Any] | None = None
    luckiest_season: dict[str, Any] | None = None
    unluckiest_season: dict[str, Any] | None = None


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


class RivalryInsights(BaseModel):
    """Bundle behind the insight bands on ``/rivalries``.

    Each band is its own availability-tagged object carrying rich, deep-linkable
    context (matchup_id, owner refs, heat components, …), so the model stays
    extra-permissive rather than enumerating a class per band. The frontend reads
    each band's ``available`` first, then its rows.
    """

    model_config = ConfigDict(extra="allow")

    records: dict[str, Any]
    streaks: dict[str, Any]
    intensity: dict[str, Any]
    nemeses: dict[str, Any]
    playoffs: dict[str, Any]


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
    nfl_opponent: str | None = None
    nfl_game_status: str | None = None
    roster_status: str | None = None
    roster_status_label: str | None = None
    reserve_eligibility_status: str | None = None
    league_points: float | None = None  # null (not 0) when unscored — see ``reason``
    is_starter: bool
    breakdown: dict[str, Any] = {}
    projection: float | None = None
    projection_delta: float | None = None
    projection_available: bool = True
    projection_reason: str | None = None
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
    context_label: str | None = None  # concise UI flag: "DNP" | "Out" | "RES + pts" | etc.
    context_detail: str | None = None  # tooltip / row detail explaining the flag
    injury_status: str | None = None  # e.g. "Out" | "Doubtful" | "Questionable"
    injury_body_part: str | None = None  # e.g. "Knee" | "Hamstring"
    injury_secondary: str | None = None  # secondary body part, non-injury notes dropped
    injury_practice_status: str | None = None  # short practice code: "DNP" | "Ltd" | "Full" | "Out"


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
    # True when this side's whole week is a reconstructed roster-audit snapshot
    # (not a live weekly capture): roster→team attribution and slots are
    # approximate. Per-player DATA drift badges are suppressed in this case in
    # favor of the single ``roster_reconstructed_note`` caveat.
    roster_reconstructed: bool = False
    roster_reconstructed_note: str | None = None
    lineup: list[BoxPlayer]


class BoxScore(BaseModel):
    matchup_id: int
    season_year: int | None = None
    week: int
    available: bool
    reason: str | None = None
    is_playoff: bool = False
    # Whether this (season, week) has real projection data — drives a single
    # top-level note rather than a per-player gap. ``projection_reason`` carries
    # the machine code (e.g. ``projections_not_captured``) for the UI copy.
    projections_available: bool = True
    projection_reason: str | None = None
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
    # A placeholder for an open roster spot at week-end (a player was dropped and
    # not replaced). Padded up to the team-season's usual roster size so the slot
    # reads as empty/dashed rather than vanishing. All other fields are null.
    is_empty: bool = False
    league_points: float | None = None  # null (not 0) for unscored slots/seasons
    zero_reason: str | None = None  # "bye" | "did_not_play" | "unexpected" | null
    zero_detail: str | None = None
    context_label: str | None = None
    context_detail: str | None = None
    acquisition_type: str | None = None
    acquisition_week: int | None = None
    injury_status: str | None = None  # e.g. "Out" | "Doubtful" | "Questionable"
    injury_body_part: str | None = None  # e.g. "Knee" | "Hamstring"
    injury_secondary: str | None = None  # secondary body part, non-injury notes dropped
    injury_practice_status: str | None = None  # short practice code: "DNP" | "Ltd" | "Full" | "Out"


class TeamRosterOut(BaseModel):
    team_id: int
    season_year: int
    week: int
    weeks_available: list[int]
    is_scored: bool
    # True when the displayed week's whole roster is a reconstructed audit
    # snapshot (not a live weekly capture): per-player attribution/slots are
    # approximate. Shown as one caveat banner, mirroring the box score.
    roster_reconstructed: bool = False
    roster_reconstructed_note: str | None = None
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
    roster_weeks: list[int]  # authoritative weeks used for the diff (audit weeks excluded)
    # Weeks dropped from the diff because their whole roster is a reconstructed
    # audit snapshot (non-authoritative); excluded to avoid fabricated churn.
    reconstructed_weeks: list[int] = []
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
