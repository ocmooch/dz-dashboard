"""fix-pass P4 — derived in-season roster moves (F-37 tier 1).

Known answers against the fixture's mav-2016 two-week scenario:
McCaffrey (drafted wk1, kept) → retain; Ravens D/ST (wk1 only) → drop at wk2;
Waiver Wendell (wk2 only) → add at wk2. Plus the no-snapshot gap case and the
not-gated-on-scoring case (mav 2015, unscored, two snapshots).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_pipeline.repository.models import (
    Base,
    League,
    Owner,
    Player,
    Season,
    Team,
    TeamRoster,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session as SASession

from ff_dashboard.analytics.teams import team_roster
from ff_dashboard.analytics.transactions import derive_roster_moves
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _by_action(moves: list[dict], action: str) -> list[dict]:
    return [m for m in moves if m["action"] == action]


def test_roster_moves_known_answer(session: Session) -> None:
    mav_2016 = KNOWN["team_id"][(2016, "mav")]
    data = derive_roster_moves(session, mav_2016)
    assert data is not None
    assert data["season_year"] == 2016
    assert data["available"] is True
    assert data["roster_weeks"] == [1, 2]

    adds = _by_action(data["moves"], "add")
    drops = _by_action(data["moves"], "drop")
    retains = _by_action(data["moves"], "retain")

    assert len(adds) == 1 and len(drops) == 1 and len(retains) == 1

    add = adds[0]
    assert add["player_id"] == KNOWN["player_id"]["wendell"]
    assert add["player_name"] == "Waiver Wendell"
    assert add["week"] == 2

    drop = drops[0]
    assert drop["player_id"] == KNOWN["player_id"]["dst"]
    assert drop["player_name"] == "Ravens D/ST"
    assert drop["week"] == 2

    retain = retains[0]
    assert retain["player_id"] == KNOWN["player_id"]["cmc"]
    assert retain["week"] == 1


def test_drafted_opening_player_is_retained_not_added(session: Session) -> None:
    """A player drafted at the opening week is a retain, never a spurious add."""
    mav_2016 = KNOWN["team_id"][(2016, "mav")]
    data = derive_roster_moves(session, mav_2016)
    assert data is not None
    cmc = KNOWN["player_id"]["cmc"]
    cmc_moves = [m for m in data["moves"] if m["player_id"] == cmc]
    assert [m["action"] for m in cmc_moves] == ["retain"]
    assert not any(m["action"] == "add" for m in cmc_moves)


def test_roster_moves_gap_when_no_snapshots(session: Session) -> None:
    """A season with <2 roster snapshots → available:false (DataGap), never zeros."""
    ice_2015 = KNOWN["team_id"][(2015, "ice")]  # no 2015 roster rows for ice
    data = derive_roster_moves(session, ice_2015)
    assert data is not None
    assert data["available"] is False
    assert data["roster_weeks"] == []
    assert data["moves"] == []


def test_roster_moves_not_gated_on_is_scored(session: Session) -> None:
    """An unscored season with >=2 snapshots still derives moves."""
    mav_2015 = KNOWN["team_id"][(2015, "mav")]
    data = derive_roster_moves(session, mav_2015)
    assert data is not None
    assert data["is_scored"] is False
    assert data["available"] is True
    assert data["roster_weeks"] == [1, 2]
    vince_moves = [m for m in data["moves"] if m["player_id"] == KNOWN["player_id"]["vince"]]
    assert [m["action"] for m in vince_moves] == ["retain"]


def test_roster_moves_unknown_team_is_none(session: Session) -> None:
    assert derive_roster_moves(session, 999999) is None


# --- Reconstructed (all-audit) week handling -------------------------------
#
# These build a tiny self-contained DB rather than perturbing the shared
# fixture's known answers. The scenario mirrors the live data that motivated the
# fix: week 1 is a non-authoritative ``audit`` snapshot whose roster differs from
# the authoritative weeks, so naively diffing against it fabricates churn.


def _audit_week_session() -> SASession:
    """A one-team season where W1 is all-``audit`` and W2/W3 are ``history``.

    W1 (audit) holds {Keep, Late}; the real weeks hold {Keep, Early}. A diff that
    trusts W1 would drop Early at W1 and add it at... etc. — the fix drops W1.
    """
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    session = SASession(engine)
    league = League(league_id="L", name="T", platform="nfl_com", current_season_year=2025)
    session.add(league)
    owner = Owner(league_id="L", display_name="O", joined_year=2025)
    session.add(owner)
    season = Season(league_id="L", year=2025, status="in_progress")
    session.add(season)
    session.flush()
    team = Team(season_id=season.season_id, owner_id=owner.owner_id, team_name="Tm")
    session.add(team)
    keep = Player(name_full="Keep Guy", position="WR")
    early = Player(name_full="Early Guy", position="RB")
    late = Player(name_full="Late Guy", position="QB")
    session.add_all([keep, early, late])
    session.flush()

    def roster(player: Player, week: int, kind: str) -> TeamRoster:
        return TeamRoster(
            team_id=team.team_id,
            player_id=player.player_id,
            season_year=2025,
            week=week,
            roster_slot=player.position,
            is_starter=True,
            extra_data={"snapshot_kind": kind},
        )

    session.add_all(
        [
            # Week 1 — entirely audit (non-authoritative): Keep + Late.
            roster(keep, 1, "audit"),
            roster(late, 1, "audit"),
            # Weeks 2 & 3 — authoritative history: Keep + Early (the real roster).
            roster(keep, 2, "history"),
            roster(early, 2, "history"),
            roster(keep, 3, "history"),
            roster(early, 3, "history"),
        ]
    )
    session.commit()
    return session


def test_roster_moves_excludes_reconstructed_audit_week() -> None:
    with _audit_week_session() as session:
        team_id = session.execute(select(Team.team_id)).scalar_one()
        data = derive_roster_moves(session, team_id)
        assert data is not None
        # W1 (all-audit) is reported but never diffed against.
        assert data["reconstructed_weeks"] == [1]
        assert data["roster_weeks"] == [2, 3]
        # "Late Guy" existed only in the bogus audit week → no move at all.
        names = {m["player_name"] for m in data["moves"]}
        assert "Late Guy" not in names
        # No fabricated W1 churn: every emitted move is at an authoritative week.
        assert all(m["week"] in (2, 3) for m in data["moves"])
        # Keep Guy spans both authoritative weeks → a single retain.
        keep_moves = [m for m in data["moves"] if m["player_name"] == "Keep Guy"]
        assert [m["action"] for m in keep_moves] == ["retain"]


def test_team_roster_flags_reconstructed_audit_week() -> None:
    with _audit_week_session() as session:
        team_id = session.execute(select(Team.team_id)).scalar_one()
        wk1 = team_roster(session, team_id, 1)
        assert wk1 is not None
        assert wk1["roster_reconstructed"] is True
        assert "audit snapshot" in (wk1["roster_reconstructed_note"] or "")
        # An authoritative week carries no caveat.
        wk2 = team_roster(session, team_id, 2)
        assert wk2 is not None
        assert wk2["roster_reconstructed"] is False
        assert wk2["roster_reconstructed_note"] is None
