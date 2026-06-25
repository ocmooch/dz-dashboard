"""The box score renders the season-correct NFL position, not the snapshot.

``players.position`` is a single current/last-known snapshot, so a player who
changed positions (or was ever mislabeled) is shown wrong for the seasons that
disagree — the reported "2014 playoff team shows Jordan Matthews playing TE in
the WR slot". ``_team_box`` now routes the position badge through
``player_season_positions`` (the season-aware store), falling back to the
snapshot only when nothing is stored.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from ff_pipeline.repository.database import Base
from ff_pipeline.repository.models import (
    League,
    Owner,
    Player,
    PlayerSeasonPosition,
    Season,
    Team,
    TeamRoster,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ff_dashboard.analytics.matchups import _team_box

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def box(tmp_path: Path) -> Iterator[tuple[Session, int, Season]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'box.db'}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as ss:
        league = League(league_id="36271", name="DZ", platform="nfl_com")
        season = Season(league_id="36271", year=2014, status="completed")
        owner = Owner(league_id="36271", display_name="Harry")
        ss.add_all([league, season, owner])
        ss.flush()
        team = Team(season_id=season.season_id, owner_id=owner.owner_id, team_name="Harry")
        # Started in a *flex* (W/R) slot: snapshot TE is the later-career mislabel,
        # so the badge must come from the 2014 season position (WR).
        jm = Player(name_full="Jordan Matthews", position="TE", gsis_id="00-0031299")
        # Started in a concrete *TE* slot while his nflverse season position is QB
        # (the fantasy-special Taysom Hill case): the slot wins → badge TE.
        hill = Player(name_full="Taysom Hill", position="TE", gsis_id="00-00hil")
        # Bench slot, no stored season position → falls back to the snapshot.
        snap = Player(name_full="Bench Benny", position="RB", gsis_id="00-00snp")
        ss.add_all([team, jm, hill, snap])
        ss.flush()
        ss.add_all(
            [
                PlayerSeasonPosition(
                    player_id=jm.player_id, season_year=2014, position="WR", source="nflverse"
                ),
                PlayerSeasonPosition(
                    player_id=hill.player_id, season_year=2014, position="QB", source="nflverse"
                ),
            ]
        )
        for player, slot in ((jm, "W/R"), (hill, "TE"), (snap, "BN")):
            ss.add(
                TeamRoster(
                    team_id=team.team_id,
                    player_id=player.player_id,
                    season_year=2014,
                    week=15,
                    roster_slot=slot,
                    is_starter=slot != "BN",
                )
            )
        ss.commit()
        yield ss, team.team_id, season
    engine.dispose()


def test_box_position_badge_resolution(
    box: tuple[Session, int, Season],
) -> None:
    session, team_id, season = box
    lineup = {p["player_name"]: p for p in _team_box(session, team_id, season, 15, None)["lineup"]}
    # Flex slot → season position (WR) overrides the mislabeled snapshot (TE).
    assert lineup["Jordan Matthews"]["position"] == "WR"
    # Concrete TE slot → the league's slot wins over the nflverse season QB.
    assert lineup["Taysom Hill"]["position"] == "TE"
    # Bench slot, no season position → snapshot stands.
    assert lineup["Bench Benny"]["position"] == "RB"
