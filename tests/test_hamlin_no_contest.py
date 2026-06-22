"""Dashboard rendering of the 2022 Week-17 Hamlin no-contest substitution.

The upstream pipeline stamps each affected wk17 roster slot with a
``hamlin_substitute`` provenance block (``wk17_partial + wk19``). The dashboard
is display-only: it must badge those slots, surface the two-component split,
suppress the now-false zero classification, and show a matchup-level banner —
all keyed off the presence of the flag, never a hardcoded id or year. The fixture
seeds the affected players on the away (goose) side of the rendered 2017 wk1 Iceman
box score (see ``conftest._populate``).

A separate, year-gated curated timeline event is also tested against a minimal
purpose-built session.
"""

from __future__ import annotations

from ff_pipeline.repository.models import Base, League, Season, Team, TeamRoster
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ff_dashboard.analytics.curated_events import curated_events_by_year
from ff_dashboard.analytics.matchups import box_score
from tests.conftest import KNOWN


def _box(session: Session) -> dict:
    # The rendered Iceman matchup: home=ice, away=goose (affected players live on
    # the goose away side).
    data = box_score(session, KNOWN["matchup_id"][(2017, 1, "ice")])
    assert data is not None
    return data


def _away_player(data: dict, player_key: str) -> dict:
    pid = KNOWN["player_id"][player_key]
    return next(p for p in data["away"]["lineup"] if p["player_id"] == pid)


def test_resolution_banner_shown(session: Session) -> None:
    data = _box(session)
    assert data["available"] is True
    assert data["resolution_note"]
    assert "no-contest" in data["resolution_note"].lower()


def test_affected_player_badged_and_split_exposed(session: Session) -> None:
    data = _box(session)
    qb = _away_player(data, "nc_qb")
    assert qb["context_label"] == "Wk17+19"
    # The false zero-classification must be suppressed (positive points, but no
    # wk17 nflverse row).
    assert qb["zero_reason"] is None
    sub = qb["hamlin_substitute"]
    assert sub is not None
    assert sub["league_points"] == 27.0
    assert sub["wk17_partial"]["points"] == 6.0
    assert sub["wk19"]["points"] == 21.0
    # The combined breakdown rides on the existing per-player breakdown field.
    assert qb["breakdown"] == {"passing": 27.0}


def test_zero_point_substitute_not_flagged_did_not_play(session: Session) -> None:
    data = _box(session)
    zeb = _away_player(data, "nc_zero")
    # Without the provenance branch, a 0.0 league result with no nflverse row
    # would classify as "did_not_play"; the flag must suppress that.
    assert zeb["zero_reason"] is None
    assert zeb["context_label"] == "Wk17+19"


def test_unaffected_matchup_has_no_resolution_note(session: Session) -> None:
    # A normal 2017 wk1 game carries no substitution → no banner.
    data = box_score(session, KNOWN["matchup_id"][(2017, 1, "mav")])
    assert data is not None
    assert data.get("resolution_note") is None


# ---------------------------------------------------------------------------
# Curated timeline event (year-gated; minimal purpose-built session)
# ---------------------------------------------------------------------------


def _minimal_session() -> Session:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(League(league_id="L1", name="Test", platform="nfl_com"))
    season = Season(league_id="L1", year=2022, status="completed")
    session.add(season)
    session.flush()
    session.add(Team(season_id=season.season_id, owner_id=1, team_name="T"))
    session.flush()
    return session


def test_curated_event_absent_without_provenance() -> None:
    session = _minimal_session()
    session.add(
        TeamRoster(
            team_id=1,
            player_id=1,
            season_year=2022,
            week=17,
            roster_slot="QB",
            is_starter=True,
            extra_data={"nfl_com_points": 5.0},
        )
    )
    session.commit()
    assert curated_events_by_year(session) == {}
    session.close()


def test_curated_event_present_with_provenance() -> None:
    session = _minimal_session()
    session.add(
        TeamRoster(
            team_id=1,
            player_id=1,
            season_year=2022,
            week=17,
            roster_slot="QB",
            is_starter=True,
            extra_data={
                "nfl_com_points": 27.34,
                "hamlin_substitute": {"basis": "no_contest_wk17partial_plus_wk19"},
            },
        )
    )
    session.commit()
    events = curated_events_by_year(session)
    assert 2022 in events
    event = events[2022][0]
    assert event["category"] == "league_event"
    assert event["tier"] == "T1"
    assert event["source"] == "league_ruling"
    assert event["certainty"] == "verified"
    assert event["changed_at"] == "2023-01-02"
    assert "no-contest" in event["summary"].lower()
    assert "smokin doubs" in event["summary"].lower()
    session.close()
