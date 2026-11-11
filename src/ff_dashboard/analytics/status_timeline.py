"""Player status across sources (Sleeper D7).

Two sources describe a player's status for a week:

- the **nflverse weekly injury report** (``player_injury_reports``): the official game status
  for that week. It lists only designated players, so a missing row inside the reported weeks
  means "not on the report", which is a real answer;
- the **Sleeper player directory snapshot** (``player_status_snapshots``, Sleeper seasons only):
  taken by the Wednesday capture after each week's games, so the newest snapshot on or before a
  week's kickoff is the status going into that week. ``queries.player_status_asof`` applies the
  7-day cutoff; nothing within 7 days is a gap.

The box score and the week-scoped team roster use :func:`week_status`: nflverse first, the
Sleeper snapshot as the fallback. The Player detail timeline (:func:`player_status_timeline`)
shows both columns side by side.

``analytics/player_status.py`` is a different job (the NFL.com current-state-drift
classifier); it is reused here, not changed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from ff_pipeline.repository import queries
from ff_pipeline.repository.models import (
    Matchup,
    PlayerInjuryReport,
    Season,
    TeamRoster,
)
from sqlalchemy import func, select

from ff_dashboard.analytics.common import played_season_ids, require_league
from ff_dashboard.analytics.injuries import InjuryFields, injury_fields
from ff_dashboard.analytics.platform import season_capabilities, season_provenance, week_state
from ff_dashboard.analytics.player_status import should_suppress_status

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ff_pipeline.repository.models import PlayerStatusSnapshot
    from sqlalchemy.orm import Session

SLEEPER = "sleeper"
NFLVERSE = "nflverse"
#: the capability key upstream reports for daily/weekly player status.
STATUS_CAPABILITY = "player_status_daily"

GAP_REPORTS_NOT_LOADED = "reports_not_loaded"
GAP_STALE_SNAPSHOT = "stale_or_missing_snapshot"
REASON_SEASON_NOT_PLAYED = "season_not_played"

# Sleeper ``injury_status`` values that are a game designation (the badge shows them).
_SLEEPER_GAME_STATUSES = {"questionable": "Questionable", "doubtful": "Doubtful", "out": "Out"}
# Sleeper ``practice_participation`` → the short code the badge uses.
_SLEEPER_PRACTICE = {"full": "Full", "limited": "Ltd", "dnp": "DNP"}


class SleeperStatus(InjuryFields):
    roster_status: str | None  # IR / PUP / Sus / NA / ... (never a badge)
    depth_chart: str | None  # "WR2"
    nfl_team: str | None
    as_of: date | None


class MergedStatus(InjuryFields):
    injury_source: str | None  # "nflverse" | "sleeper" | None
    injury_as_of: date | None  # the Sleeper snapshot date; None for nflverse
    sleeper_roster_status: str | None  # feeds the IR-slot eligibility text only


def week_kickoff(year: int, week: int) -> date:
    """The Thursday that opens NFL ``week`` of ``year``.

    Week 1 is the Thursday after Labor Day (the first Monday of September); each later week is
    7 days on. A calendar rule, right for every season since 2010; used only to pick which
    Sleeper snapshot describes a week."""
    sept1 = date(year, 9, 1)
    labor_day = sept1 + timedelta(days=(0 - sept1.weekday()) % 7)
    return labor_day + timedelta(days=3 + 7 * (week - 1))


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def sleeper_status_fields(snap: PlayerStatusSnapshot | None) -> SleeperStatus:
    """One Sleeper snapshot mapped onto the badge field set.

    Questionable / Doubtful / Out become ``injury_status`` (the badge). Every other value
    (IR, PUP, Sus, NA, COV, DNR, or anything new) becomes ``roster_status``: shown on the
    timeline, never as a badge."""
    if snap is None:
        return SleeperStatus(
            injury_status=None,
            injury_body_part=None,
            injury_secondary=None,
            injury_practice_status=None,
            roster_status=None,
            depth_chart=None,
            nfl_team=None,
            as_of=None,
        )
    raw = _clean(snap.injury_status)
    game = _SLEEPER_GAME_STATUSES.get(raw.lower()) if raw else None
    practice = _clean(snap.practice_participation)
    depth_pos = _clean(snap.depth_chart_position)
    depth = f"{depth_pos}{snap.depth_chart_order}" if depth_pos and snap.depth_chart_order else None
    return SleeperStatus(
        injury_status=game,
        injury_body_part=_clean(snap.injury_body_part),
        injury_secondary=None,
        injury_practice_status=_SLEEPER_PRACTICE.get(practice.lower()) if practice else None,
        roster_status=raw if raw and game is None else None,
        depth_chart=depth,
        nfl_team=_clean(snap.nfl_team),
        as_of=snap.as_of_date,
    )


def _first_in_cluster(found: Mapping[int, Any], members: Iterable[int]) -> Any | None:
    for member in members:
        hit = found.get(member)
        if hit is not None:
            return hit
    return None


def _all_members(player_ids: Iterable[int], cluster_members: Mapping[int, list[int]]) -> set[int]:
    out: set[int] = set()
    for pid in player_ids:
        out.update(cluster_members.get(pid, [pid]))
    return out


def _is_sleeper(session: Session, season: Season) -> bool:
    return season_provenance(session, season.season_id)["platform"] == SLEEPER


def week_status(
    session: Session,
    season: Season,
    week: int,
    player_ids: Iterable[int],
    cluster_members: Mapping[int, list[int]],
) -> dict[int, MergedStatus]:
    """``player_id → MergedStatus`` for one week: nflverse first, Sleeper snapshot fallback.

    Players with neither source are absent (the caller uses :func:`empty_status`)."""
    ids = list(player_ids)
    reports = queries.injury_reports_for_week(session, season.year, week)
    snaps: dict[int, PlayerStatusSnapshot] = {}
    if _is_sleeper(session, season):
        snaps = queries.player_status_asof(
            session, sorted(_all_members(ids, cluster_members)), week_kickoff(season.year, week)
        )
    out: dict[int, MergedStatus] = {}
    for pid in ids:
        members = cluster_members.get(pid, [pid])
        report = _first_in_cluster(reports, members)
        sleeper = sleeper_status_fields(_first_in_cluster(snaps, members))
        if report is not None:
            out[pid] = MergedStatus(
                **injury_fields(report),
                injury_source=NFLVERSE,
                injury_as_of=None,
                sleeper_roster_status=sleeper["roster_status"],
            )
        elif sleeper["as_of"] is not None:
            has_designation = any(
                sleeper[k]  # type: ignore[literal-required]
                for k in ("injury_status", "injury_body_part", "injury_practice_status")
            )
            out[pid] = MergedStatus(
                injury_status=sleeper["injury_status"],
                injury_body_part=sleeper["injury_body_part"],
                injury_secondary=None,
                injury_practice_status=sleeper["injury_practice_status"],
                injury_source=SLEEPER if has_designation else None,
                injury_as_of=sleeper["as_of"] if has_designation else None,
                sleeper_roster_status=sleeper["roster_status"],
            )
    return out


def empty_status() -> MergedStatus:
    return MergedStatus(
        **injury_fields(None),
        injury_source=None,
        injury_as_of=None,
        sleeper_roster_status=None,
    )


def for_player(merged: Mapping[int, MergedStatus], player_id: int, *, played: bool) -> MergedStatus:
    """The player's merged status, with a stale Sleeper "Out" dropped for a player who played.

    The Sleeper snapshot is from the Wednesday before the games, so a player who then played
    cannot truthfully read "Out". nflverse rows are the week's official report and are kept as
    they were before D7."""
    status = merged.get(player_id) or empty_status()
    if status["injury_source"] != SLEEPER or not played:
        return status
    if not should_suppress_status(status["injury_status"], played=played):
        return status
    cleared = MergedStatus(**{**status, "injury_status": None})
    if not (cleared["injury_body_part"] or cleared["injury_practice_status"]):
        cleared["injury_source"] = None
        cleared["injury_as_of"] = None
    return cleared


def badge_fields(status: MergedStatus) -> dict[str, Any]:
    """The fields a box-score / roster player row carries (``sleeper_roster_status`` stays
    internal: it only feeds the IR-slot eligibility text)."""
    return {k: v for k, v in status.items() if k != "sleeper_roster_status"}


# ---------------------------------------------------------------------------
# Player detail timeline
# ---------------------------------------------------------------------------


def _report_entry(report: PlayerInjuryReport) -> dict[str, Any]:
    return {
        "source": NFLVERSE,
        "as_of": None,
        **injury_fields(report),
        "roster_status": None,
        "depth_chart": None,
        "nfl_team": None,
    }


def _snapshot_entry(snap: PlayerStatusSnapshot) -> dict[str, Any]:
    fields = sleeper_status_fields(snap)
    return {"source": SLEEPER, **fields}


def _cluster(session: Session, player_id: int) -> list[int]:
    # Lazy import: matchups imports this module.
    from ff_dashboard.analytics.matchups import _identity_cluster_members

    return _identity_cluster_members(session, [player_id]).get(player_id, [player_id])


def default_status_season(session: Session, player_id: int) -> int | None:
    """The latest played season the player was rostered in, else the latest played season."""
    played = played_season_ids(session)
    if not played:
        return None
    members = _cluster(session, player_id)
    rostered = session.scalars(
        select(func.max(Season.year))
        .join(TeamRoster, TeamRoster.season_year == Season.year)
        .where(TeamRoster.player_id.in_(members), Season.season_id.in_(played))
    ).first()
    if rostered is not None:
        return int(rostered)
    return session.scalars(
        select(func.max(Season.year)).where(Season.season_id.in_(played))
    ).first()


def player_status_timeline(
    session: Session, player_id: int, season_year: int, *, today: date | None = None
) -> dict[str, Any] | None:
    """Week-by-week status for one player in one season; ``None`` for an unknown player."""
    player = queries.get_player(session, player_id)
    if player is None:
        return None
    league = require_league(session)
    season = queries.get_season_by_year(session, league.league_id, season_year)
    base: dict[str, Any] = {
        "player_id": player_id,
        "season_year": season_year,
        "platform": None,
        "platform_label": None,
        "available": False,
        "reason": REASON_SEASON_NOT_PLAYED,
        "has_snapshots": False,
        "snapshot_capability": None,
        "is_provisional": False,
        "latest": None,
        "weeks": [],
    }
    if season is None or season.season_id not in played_season_ids(session):
        return base

    members = _cluster(session, player_id)
    prov = season_provenance(session, season.season_id)
    sleeper = prov["platform"] == SLEEPER
    state = week_state(session, season.season_id)
    weeks = [
        int(w)
        for w in session.scalars(
            select(Matchup.week).where(Matchup.season_id == season.season_id).distinct()
        )
    ]
    weeks.sort()

    reports = list(
        session.scalars(
            select(PlayerInjuryReport).where(
                PlayerInjuryReport.season_year == season.year,
                PlayerInjuryReport.player_id.in_(members),
            )
        )
    )
    by_week: dict[int, dict[int, PlayerInjuryReport]] = {}
    for r in reports:
        by_week.setdefault(r.week, {})[r.player_id] = r
    last_reported = session.scalars(
        select(func.max(PlayerInjuryReport.week)).where(
            PlayerInjuryReport.season_year == season.year
        )
    ).first()

    rows: list[dict[str, Any]] = []
    for week in weeks:
        kickoff = week_kickoff(season.year, week)
        report = _first_in_cluster(by_week.get(week, {}), members)
        game_gap = None
        if report is None and (last_reported is None or week > last_reported):
            game_gap = GAP_REPORTS_NOT_LOADED
        snapshot = None
        snapshot_gap = None
        if sleeper:
            snap = _first_in_cluster(queries.player_status_asof(session, members, kickoff), members)
            if snap is None:
                snapshot_gap = GAP_STALE_SNAPSHOT
            else:
                snapshot = _snapshot_entry(snap)
        rows.append(
            {
                "week": week,
                "kickoff_date": kickoff,
                "game_report": _report_entry(report) if report is not None else None,
                "game_report_gap": game_gap,
                "snapshot": snapshot,
                "snapshot_gap": snapshot_gap,
            }
        )

    latest = None
    if sleeper and not state["is_final"]:
        snap = _first_in_cluster(
            queries.player_status_asof(session, members, today or date.today()), members
        )
        latest = _snapshot_entry(snap) if snap is not None else None

    caps = season_capabilities(session, season.season_id)
    return {
        **base,
        "platform": prov["platform"],
        "platform_label": prov["platform_label"],
        "available": True,
        "reason": None,
        "has_snapshots": sleeper,
        "snapshot_capability": caps.get(STATUS_CAPABILITY),
        "is_provisional": not state["is_final"],
        "latest": latest,
        "weeks": rows,
    }
