"""Mixed-era fixture DB (Sleeper D0): the legacy NFL.com fixture + one Sleeper 2026 season.

The Sleeper season is loaded through ff-pipeline's packaged loader (``load_league_season``) from
upstream's pseudonymized fixtures (``../danger-zone/tests/fixtures/sleeper_league``), the same
path as upstream ``tests/integration/test_sleeper_load.py``. Running pipeline loaders here is
approved for tests only (``docs/sleeper/00_UPSTREAM_STATE.md`` §7); ``src/`` stays read-only.

Upstream's helpers (``OverlaySource``, ``fixture_league``) live in its test package, which isn't
installed, so the few lines needed are re-implemented below.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import ff_pipeline
from ff_pipeline.crawlers.sleeper_league.archive_view import load_league
from ff_pipeline.crawlers.sleeper_league.client import FixtureSleeperLeagueSource
from ff_pipeline.crawlers.sleeper_league.runner import load_league_season
from ff_pipeline.repository.models import Owner, OwnerPlatformIdentity, Player, Season
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from ff_pipeline.crawlers.sleeper_league.client import FetchedPayload
    from ff_pipeline.crawlers.sleeper_league.endpoints import PayloadRequest

#: upstream fixture root, found through the editable ff-pipeline install (CI checks out
#: danger-zone ``dev`` as ``../danger-zone``).
FX = Path(ff_pipeline.__file__).resolve().parents[2] / "tests" / "fixtures" / "sleeper_league"
SLEEPER_LEAGUE = "900000000000000001"
SLEEPER_YEAR = 2026
#: legacy fixture owners that continue into the Sleeper era (shared owners, `01` §8).
SHARED_OWNERS = ("Maverick", "Iceman", "Goose", "Viper")


@dataclass(frozen=True)
class OverlaySource:
    """Upstream's synthetic scenario files (co-owner, pick + FAAB trade, commissioner override,
    traded pick) replace their ``season_2026`` namesakes."""

    def get(self, request: PayloadRequest) -> FetchedPayload:
        if (FX / "synthetic" / request.fixture_name).exists():
            return FixtureSleeperLeagueSource(FX / "synthetic").get(request)
        payload = FixtureSleeperLeagueSource(FX / "season_2026").get(request)
        if request.fixture_name == COMMISSIONER_WEEK_FILE:
            return _with_commissioner_move(payload)
        return payload


#: Upstream's fixtures have no commissioner move, so week 2 gets one: a copy of its first
#: free-agent move re-typed ``commissioner`` (the loader tags it ``by_commissioner``).
COMMISSIONER_WEEK_FILE = f"v1_league_{SLEEPER_LEAGUE}_transactions_2.json"
COMMISSIONER_TX_ID = "900000000299999999"


def _with_commissioner_move(payload: FetchedPayload) -> FetchedPayload:
    moves = json.loads(payload.body)
    template = next(m for m in moves if m.get("type") == "free_agent")
    moves.append({**template, "type": "commissioner", "transaction_id": COMMISSIONER_TX_ID})
    return dataclasses.replace(payload, body=json.dumps(moves).encode())


def build_mixed_era_db(legacy_db: Path, out: Path, league_id: str) -> Path:
    """Copy ``legacy_db`` to ``out`` and load the Sleeper 2026 season into the copy."""
    src = sqlite3.connect(f"file:{legacy_db}?mode=ro", uri=True)
    dst = sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    data = load_league(OverlaySource(), SLEEPER_LEAGUE)
    users = sorted(str(u["user_id"]) for u in data.users)
    engine = create_engine(f"sqlite:///{out}", future=True)
    try:
        with Session(engine) as ss:
            ss.add(
                Season(
                    league_id=league_id,
                    year=SLEEPER_YEAR,
                    status="in_progress",
                    platform="sleeper",
                    platform_league_id=SLEEPER_LEAGUE,
                )
            )
            by_name = {
                o.display_name: o.owner_id
                for o in ss.scalars(select(Owner).where(Owner.display_name.in_(SHARED_OWNERS)))
            }
            for i, user_id in enumerate(users):
                if i < len(SHARED_OWNERS):
                    owner_id = by_name[SHARED_OWNERS[i]]
                else:
                    o = Owner(
                        league_id=league_id, display_name=f"Sleeper Owner {i + 1}", joined_year=2026
                    )
                    ss.add(o)
                    ss.flush()
                    owner_id = o.owner_id
                ss.add(
                    OwnerPlatformIdentity(
                        owner_id=owner_id, platform="sleeper", external_user_id=user_id
                    )
                )
            for sid in sorted(set(data.players) | {str(p["player_id"]) for p in data.draft_picks}):
                info = data.players.get(sid) or {}
                name = " ".join(x for x in (info.get("first_name"), info.get("last_name")) if x)
                ss.add(
                    Player(
                        name_full=name or f"Drafted {sid}",
                        position=info.get("position"),
                        nfl_team=info.get("team"),
                        sleeper_id=sid,
                        is_active=True,
                    )
                )
            ss.commit()
            load_league_season(ss, OverlaySource(), SLEEPER_LEAGUE, franchise_league_id=league_id)
            ss.commit()
    finally:
        engine.dispose()
    return out
