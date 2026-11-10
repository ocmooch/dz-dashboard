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
from typing import TYPE_CHECKING, Any

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


def build_mixed_era_db(
    legacy_db: Path, out: Path, league_id: str, *, decided: bool = False
) -> Path:
    """Copy ``legacy_db`` to ``out`` and load the Sleeper 2026 season into the copy.

    ``decided`` loads :class:`DecidedSource` instead: weeks 6-8 are a fully decided 6+6 playoff.
    """
    source: OverlaySource = DecidedSource() if decided else OverlaySource()
    src = sqlite3.connect(f"file:{legacy_db}?mode=ro", uri=True)
    dst = sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    data = load_league(source, SLEEPER_LEAGUE)
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
            load_league_season(ss, source, SLEEPER_LEAGUE, franchise_league_id=league_id)
            ss.commit()
    finally:
        engine.dispose()
    return out


#: Decided-bracket variant (D5), after upstream ``test_sleeper_rich._decided``: the playoffs start
#: in week 6, seeds are by points over weeks 1-5, and the higher real score wins every bracket game.
DECIDED_PLAYOFF_WEEK_START = 6
_LEAGUE_FILE = f"v1_league_{SLEEPER_LEAGUE}.json"
_AFTER_PLAYOFFS_FILE = f"v1_league_{SLEEPER_LEAGUE}_matchups_9.json"
_PLAYOFF_MATCHUP_FILES = {
    f"v1_league_{SLEEPER_LEAGUE}_matchups_{DECIDED_PLAYOFF_WEEK_START - 1 + r}.json": r
    for r in (1, 2, 3)
}
_BRACKET_FILES = {
    f"v1_league_{SLEEPER_LEAGUE}_winners_bracket.json": slice(0, 6),
    f"v1_league_{SLEEPER_LEAGUE}_losers_bracket.json": slice(6, 12),
}


def _six_team_bracket(
    seeds: list[int], score: dict[tuple[int, int], float]
) -> list[dict[str, Any]]:
    """Sleeper's 6-team shape (upstream ``test_sleeper_brackets._bracket``), decided by score."""
    s1, s2, s3, s4, s5, s6 = seeds
    ms: list[dict[str, Any]] = [
        {"r": 1, "m": 1, "t1": s3, "t2": s6},
        {"r": 1, "m": 2, "t1": s4, "t2": s5},
        {"r": 2, "m": 3, "t1": s1, "t2_from": {"w": 1}},
        {"r": 2, "m": 4, "t1": s2, "t2_from": {"w": 2}},
        {"r": 2, "m": 5, "p": 5, "t1_from": {"l": 1}, "t2_from": {"l": 2}},
        {"r": 3, "m": 6, "p": 1, "t1_from": {"w": 3}, "t2_from": {"w": 4}},
        {"r": 3, "m": 7, "p": 3, "t1_from": {"l": 3}, "t2_from": {"l": 4}},
    ]
    by = {m["m"]: m for m in ms}
    for m in ms:
        for side in ("t1", "t2"):
            frm = m.get(f"{side}_from")
            if frm:
                ((kind, src),) = frm.items()
                m[side] = by[src][kind]
        wk = DECIDED_PLAYOFF_WEEK_START - 1 + m["r"]
        a, b = m["t1"], m["t2"]
        m["w"], m["l"] = (a, b) if score[(a, wk)] >= score[(b, wk)] else (b, a)
    return ms


def _matchup_scores() -> dict[tuple[int, int], float]:
    out: dict[tuple[int, int], float] = {}
    for wk in range(1, 9):
        path = FX / "season_2026" / f"v1_league_{SLEEPER_LEAGUE}_matchups_{wk}.json"
        for m in json.loads(path.read_text()):
            out[(int(m["roster_id"]), wk)] = float(m.get("points") or 0)
    return out


def decided_brackets() -> dict[str, list[dict[str, Any]]]:
    """``{fixture file: bracket}`` for both decided brackets (also used by tests as the answer)."""
    score = _matchup_scores()
    regular = range(1, DECIDED_PLAYOFF_WEEK_START)
    by_points = sorted(range(1, 13), key=lambda r: -sum(score[(r, w)] for w in regular))
    return {name: _six_team_bracket(by_points[sl], score) for name, sl in _BRACKET_FILES.items()}


def _paired_by_bracket(rows: list[dict[str, Any]], rnd: int) -> list[dict[str, Any]]:
    """Pair a playoff week the way Sleeper does: one matchup id per bracket game of round ``rnd``;
    a team with no game that week (a bye, or already placed) gets ``matchup_id`` null."""
    mid: dict[int, int] = {}
    games = [m for b in decided_brackets().values() for m in b if m["r"] == rnd]
    for n, m in enumerate(games, start=1):
        mid[m["t1"]] = mid[m["t2"]] = n
    return [{**r, "matchup_id": mid.get(int(r["roster_id"]))} for r in rows]


@dataclass(frozen=True)
class DecidedSource(OverlaySource):
    def get(self, request: PayloadRequest) -> FetchedPayload:
        payload = super().get(request)
        name = request.fixture_name
        if name in _BRACKET_FILES:
            body: Any = decided_brackets()[name]
        elif name in _PLAYOFF_MATCHUP_FILES:
            body = _paired_by_bracket(json.loads(payload.body), _PLAYOFF_MATCHUP_FILES[name])
        elif name == _AFTER_PLAYOFFS_FILE:
            body = []  # a real season has no games after its final
        elif name == _LEAGUE_FILE:
            body = json.loads(payload.body)
            body["settings"] = {
                **body["settings"],
                "playoff_week_start": DECIDED_PLAYOFF_WEEK_START,
            }
        else:
            return payload
        return dataclasses.replace(payload, body=json.dumps(body).encode())
