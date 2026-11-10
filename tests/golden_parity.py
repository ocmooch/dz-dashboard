"""Legacy golden snapshots (Sleeper D0): request matrix, runner and the parity comparison.

Shared by ``scripts/snapshot_legacy_payloads.py`` (writes and checks the live golden set) and
``tests/test_legacy_parity.py`` (fixture + live parity). Everything here is read-only: requests
run in-process against ``create_readonly_engine`` (``PRAGMA query_only``).

Comparison rule (plan ``docs/plans/sleeper-d0-golden-snapshots.md``): ``golden ⊆ current``.
Every golden key/value must be present and equal; new keys are allowed (additive contract
changes), list lengths and order must match, and per-request volatile paths are skipped.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi.testclient import TestClient

from ff_dashboard.api.main import create_app
from ff_dashboard.cache import AnalyticsCache
from ff_dashboard.engine import create_readonly_engine

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

#: Representative legacy seasons for the live matrix (plan "Request matrix").
LIVE_YEARS = (2010, 2013, 2016, 2020, 2024, 2025)
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
TEAM_ENDPOINTS = (
    "",
    "/roster",
    "/roster?week=1",
    "/schedule",
    "/scoring-trend",
    "/transactions",
    "/roster-moves",
    "/faab-budget",
)
SEASON_ENDPOINTS = (
    "",
    "/standings",
    "/standings?through_week=5",
    "/standings/insights",
    "/standings/timeline",
    "/weekly-scores",
    "/efficiency",
    "/bracket",
    "/conferences",
    "/power",
    "/power?through_week=5",
    "/power/timeline",
    "/draft",
    "/draft/value",
)
GLOBAL_PATHS = (
    "/v1/meta",
    "/v1/meta/coverage",
    "/v1/meta/capabilities",
    "/v1/league/overview",
    "/v1/league/timeline",
    "/v1/league/eras",
    "/v1/league/stories",
    "/v1/league/managers",
    "/v1/owners",
    "/v1/owners/rivalry-matrix",
    "/v1/records",
    "/v1/records/championships",
    "/v1/records/draft",
    "/v1/rivalries/insights",
    "/v1/draft/tendencies",
    "/v1/seasons",
    "/v1/seasons/current",
    "/v1/teams",
    "/v1/players",
    "/v1/players?position=QB&limit=500",
    "/v1/search?q=a",
    "/v1/search?q=e&limit=50",
)


@dataclass(frozen=True)
class Req:
    """One golden request. ``pinned`` = scoped to one legacy season (or a legacy team/matchup),
    so its answer must not change when a newer season is loaded; ``global`` ones (all-time,
    defaults) legitimately change once newer games count."""

    url: str
    pinned: bool
    binary: bool = False


def _q(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[tuple[Any, ...]]:
    return conn.execute(sql, tuple(params)).fetchall()


def build_matrix(db_path: Path, years: Iterable[int] | None = None) -> list[Req]:
    """Deterministic request list for the legacy seasons of ``db_path``.

    ``years=None`` takes every NFL.com season in the DB (fixture use).
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = _q(
            conn,
            "SELECT season_id, year, coalesce(regular_season_weeks, 0) FROM seasons"
            " WHERE coalesce(platform, 'nfl_com') = 'nfl_com' ORDER BY year",
        )
        wanted = set(years) if years is not None else {r[1] for r in rows}
        seasons = [r for r in rows if r[1] in wanted]
        reqs: list[Req] = [Req(p, pinned=False) for p in GLOBAL_PATHS]
        for sid, year, reg_weeks in seasons:
            reqs += [Req(f"/v1/seasons/{sid}{e}", pinned=True) for e in SEASON_ENDPOINTS]
            reqs.append(Req(f"/v1/lab/insights/{sid}", pinned=True))
            weeks = sorted({w for w in (1, reg_weeks, reg_weeks + 1) if w >= 1})
            reqs += [Req(f"/v1/seasons/{sid}/weeks/{w}/matchups", pinned=True) for w in weeks]
            reqs += [
                Req(f"/v1/stats/top-scorers?season={year}", pinned=True),
                Req(f"/v1/stats/top-scorers?season={year}&week=1", pinned=True),
                Req(f"/v1/stats/top-scorers?season={year}&position=QB&limit=100", pinned=True),
                Req(f"/v1/stats/season-totals?season={year}", pinned=True),
                Req(f"/v1/stats/season-totals?season={year}&position=RB", pinned=True),
            ]
            for playoff in (0, 1):
                m = _q(
                    conn,
                    "SELECT min(matchup_id) FROM matchups WHERE season_id = ? AND is_playoff = ?",
                    (sid, playoff),
                )
                if m and m[0][0] is not None:
                    reqs.append(Req(f"/v1/matchups/{m[0][0]}/box-score", pinned=True))
            teams = [
                r[0]
                for r in _q(
                    conn, "SELECT team_id FROM teams WHERE season_id = ? ORDER BY team_id", (sid,)
                )
            ]
            for tid in teams:
                reqs += [Req(f"/v1/teams/{tid}{e}", pinned=True) for e in TEAM_ENDPOINTS]
            for pid in _season_players(conn, sid):
                reqs += [
                    Req(f"/v1/players/{pid}/scoring?season={year}", pinned=True),
                    Req(f"/v1/players/{pid}/availability?season={year}", pinned=True),
                ]
        players = sorted(
            {int(u.split("/")[3]) for u in (r.url for r in reqs) if u.startswith("/v1/players/")}
        )
        for pid in players:
            reqs += [
                Req(f"/v1/players/{pid}", pinned=False),
                Req(f"/v1/players/{pid}/ownership", pinned=False),
                Req(f"/v1/players/{pid}/insights", pinned=False),
            ]
        owners = [r[0] for r in _q(conn, "SELECT owner_id FROM owners ORDER BY owner_id")]
        for oid in owners:
            reqs += [
                Req(f"/v1/owners/{oid}", pinned=False),
                Req(f"/v1/owners/{oid}/seasons", pinned=False),
                Req(f"/v1/owners/{oid}/story", pinned=False),
                Req(f"/v1/owners/{oid}/trajectory", pinned=False),
            ]
        first = owners[:4]
        reqs += [
            Req(f"/v1/owners/{a}/head-to-head/{b}", pinned=False)
            for i, a in enumerate(first)
            for b in first[i + 1 :]
        ]
        # Avatars: every selected team that has one (bytes hashed), plus one without (the 404).
        sids = [s[0] for s in seasons]
        if sids:
            marks = ",".join("?" * len(sids))
            with_avatar = _q(
                conn,
                f"SELECT team_id FROM teams WHERE season_id IN ({marks})"
                " AND team_avatar_asset_id IS NOT NULL ORDER BY team_id",
                sids,
            )
            without = _q(
                conn,
                f"SELECT min(team_id) FROM teams WHERE season_id IN ({marks})"
                " AND team_avatar_asset_id IS NULL",
                sids,
            )
            for (tid,) in [*with_avatar, *[w for w in without if w[0] is not None]]:
                reqs.append(Req(f"/v1/teams/{tid}/avatar", pinned=True, binary=True))
        seen: set[str] = set()
        return [r for r in reqs if not (r.url in seen or seen.add(r.url))]
    finally:
        conn.close()


def _season_players(conn: sqlite3.Connection, season_id: int) -> list[int]:
    """Top scorer per position, plus one rostered-but-unscored player (a scoring gap)."""
    out: list[int] = []
    for pos in POSITIONS:
        r = _q(
            conn,
            "SELECT s.player_id FROM player_stats_scored s JOIN players p USING (player_id)"
            " WHERE s.season_id = ? AND p.position = ? GROUP BY s.player_id"
            " ORDER BY sum(s.total_points) DESC, s.player_id LIMIT 1",
            (season_id, pos),
        )
        if r:
            out.append(int(r[0][0]))
    gap = _q(
        conn,
        "SELECT min(r.player_id) FROM team_rosters r JOIN teams t USING (team_id)"
        " WHERE t.season_id = ? AND r.player_id IS NOT NULL AND NOT EXISTS ("
        "  SELECT 1 FROM player_stats_scored s WHERE s.player_id = r.player_id AND s.season_id = ?)",
        (season_id, season_id),
    )
    if gap and gap[0][0] is not None:
        out.append(int(gap[0][0]))
    return out


@dataclass
class Response:
    status: int
    body: Any  # parsed JSON, or the sha256 hex of a binary body

    def to_json(self) -> dict[str, Any]:
        return {"status": self.status, "body": self.body}


@contextmanager
def client_for(db_path: Path, assets_root: Path | None = None) -> Iterator[TestClient]:
    engine = create_readonly_engine(f"sqlite:///{db_path}")
    try:
        app = create_app(engine, cache=AnalyticsCache(), cors_origins=[], assets_root=assets_root)
        with TestClient(app) as c:
            yield c
    finally:
        engine.dispose()


def fetch(client: TestClient, req: Req) -> Response:
    r = client.get(req.url)
    if req.binary:
        return Response(r.status_code, hashlib.sha256(r.content).hexdigest())
    try:
        body = r.json()
    except ValueError:
        body = {"_non_json_sha256": hashlib.sha256(r.content).hexdigest()}
    return Response(r.status_code, body)


# --- comparison --------------------------------------------------------------------------


def volatile_paths(a: Any, b: Any, path: str = "") -> list[str]:
    """JSON paths whose values differ between two runs of the same request (timestamps etc.)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for k in sorted(set(a) | set(b)):
            out += volatile_paths(a.get(k), b.get(k), f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [
            p
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for p in volatile_paths(x, y, f"{path}[{i}]")
        ]
    return [] if a == b else [path or "."]


def strip_paths(obj: Any, excluded: Iterable[str]) -> Any:
    ex = set(excluded)

    def walk(o: Any, path: str) -> Any:
        if isinstance(o, dict):
            return {k: walk(v, f"{path}.{k}") for k, v in o.items() if f"{path}.{k}" not in ex}
        if isinstance(o, list):
            return [walk(v, f"{path}[{i}]") for i, v in enumerate(o)]
        return o

    return walk(obj, "")


def canonical_sha(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def subset_diffs(golden: Any, current: Any, path: str = "", limit: int = 5) -> list[str]:
    """Where ``current`` fails to contain ``golden``. Paths only + short scalar reprs."""
    out: list[str] = []

    def walk(g: Any, c: Any, p: str) -> None:
        if len(out) >= limit:
            return
        if isinstance(g, dict):
            if not isinstance(c, dict):
                out.append(f"{p or '.'}: object became {type(c).__name__}")
                return
            for k, v in g.items():
                if k not in c:
                    out.append(f"{p}.{k}: missing")
                else:
                    walk(v, c[k], f"{p}.{k}")
            return
        if isinstance(g, list):
            if not isinstance(c, list) or len(c) != len(g):
                out.append(
                    f"{p or '.'}: list length {len(g)} -> {len(c) if isinstance(c, list) else type(c).__name__}"
                )
                return
            for i, (x, y) in enumerate(zip(g, c, strict=True)):
                walk(x, y, f"{p}[{i}]")
            return
        if g != c or type(g) is not type(c):
            out.append(f"{p or '.'}: {_short(g)} -> {_short(c)}")

    walk(golden, current, path)
    return out


def _short(v: Any) -> str:
    """Scalars only, truncated, so failure output never dumps payloads (real names)."""
    if isinstance(v, (dict, list)):
        return type(v).__name__
    s = repr(v)
    return s if len(s) <= 24 else s[:21] + "..."


def slug(url: str) -> str:
    safe = url.strip("/").replace("/", "_").replace("?", "__").replace("&", "_").replace("=", "-")
    return f"{safe}.json"
