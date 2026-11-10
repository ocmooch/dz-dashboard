"""Sleeper D6: the transaction market — FAAB spend, bid wars, trades with every asset, the pick
ledger, and the legacy failed-bids capability gap."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from ff_dashboard.analytics.faab_market import faab_bid, season_faab_market, team_failed_bids
from ff_dashboard.analytics.picks import league_pick_ledger
from ff_dashboard.analytics.teams import team_trades
from ff_dashboard.engine import create_readonly_engine
from tests.conftest import KNOWN
from tests.sleeper_fixture import SLEEPER_YEAR

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from fastapi.testclient import TestClient


def _rows(db: Path, sql: str, *args: Any) -> list[tuple[Any, ...]]:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return c.execute(sql, args).fetchall()
    finally:
        c.close()


def _sid(db: Path) -> int:
    return int(_rows(db, "SELECT season_id FROM seasons WHERE year=?", SLEEPER_YEAR)[0][0])


def _session(db: Path) -> Iterator[Session]:
    eng = create_readonly_engine(f"sqlite:///{db}")
    with Session(eng) as s:
        yield s
    eng.dispose()


def _trade_pair(db: Path) -> tuple[int, int]:
    """(team that sent the pick, team that received it) for the fixture's pick + FAAB trade."""
    rows = _rows(
        db,
        "SELECT team_id, counterpart_team_id FROM transactions WHERE season_id=? AND "
        "transaction_type='trade' AND player_id IS NULL AND "
        "json_array_length(json_extract(extra_data,'$.picks_out')) > 0",
        _sid(db),
    )
    ((sender, receiver),) = rows
    return int(sender), int(receiver)


# --- bid wars / FAAB market -----------------------------------------------------------------


def test_bid_war_known_answer(mixed_era_db_path: Path):
    for s in _session(mixed_era_db_path):
        m = season_faab_market(s, _sid(mixed_era_db_path))
        assert m is not None and m["is_faab_era"] and m["budget"] == 100.0
        (war,) = [w for w in m["bid_wars"] if w["week"] == 4 and w["player"]["player_id"] == 68]
        assert war["winning_bid"] == 7.0 and war["margin"] == 3.0
        assert [(b["bid"], b["won"]) for b in war["bids"]] == [(7.0, True), (4.0, False)]
        assert war["bids"][1]["failure_reason"]


def test_every_failed_claim_is_accounted_for(mixed_era_db_path: Path):
    sid = _sid(mixed_era_db_path)
    failed = _rows(
        mixed_era_db_path,
        "SELECT team_id, effective_week, player_id FROM transactions WHERE season_id=? AND status='failed'",
        sid,
    )
    for s in _session(mixed_era_db_path):
        m = season_faab_market(s, sid)
        assert m is not None
        in_wars = sum(1 for w in m["bid_wars"] for b in w["bids"] if not b["won"])
        per_team = {t["team"]["team_id"]: t["failed_bids"] for t in m["teams"]}
        assert sum(per_team.values()) == len(failed)
        by_team = sum(len(team_failed_bids(s, tid)) for tid in per_team)
        assert by_team == len(failed) and in_wars <= len(failed)
        # a war always has a lost claim and at least two claims
        assert all(len(w["bids"]) >= 2 and any(not b["won"] for b in w["bids"]) for w in m["bid_wars"])


def test_spend_counts_winning_bids_only(mixed_era_db_path: Path):
    sid = _sid(mixed_era_db_path)
    rows = _rows(
        mixed_era_db_path,
        "SELECT team_id, extra_data FROM transactions WHERE season_id=? AND "
        "transaction_type='waiver_add' AND status='complete'",
        sid,
    )
    import json

    want: dict[int, float] = {}
    for tid, extra in rows:
        bid = faab_bid(json.loads(extra) if extra else None)
        if bid is not None:
            want[int(tid)] = want.get(int(tid), 0.0) + bid
    for s in _session(mixed_era_db_path):
        m = season_faab_market(s, sid)
        assert m is not None
        for t in m["teams"]:
            spent = round(want.get(t["team"]["team_id"], 0.0), 2)
            assert t["spent"] == spent
            assert t["pct_of_budget"] == round(spent / 100.0, 4)
        assert all(b["bid"] is not None for b in m["top_bids"])
        assert [b["bid"] for b in m["top_bids"]] == sorted((b["bid"] for b in m["top_bids"]), reverse=True)


def test_zero_bid_is_a_real_bid():
    assert faab_bid({"faab_bid": 0}) == 0.0
    assert faab_bid({"faab_bid": None}) is None
    assert faab_bid({"faab_bid": "x", "bid": 3}) == 3.0


def test_legacy_market_shows_the_failed_bids_gap(session: Session, client: TestClient):
    sid = KNOWN["season_id"][2017]
    m = season_faab_market(session, sid)
    assert m is not None and m["is_faab_era"] is True
    assert m["failed_bids_capability"]["state"] == "not_on_platform"
    assert m["bid_wars"] == []
    assert all(t["failed_bids"] is None for t in m["teams"])  # a gap, never 0
    assert sum(t["winning_bids"] for t in m["teams"]) == 3
    body = client.get(f"/v1/seasons/{sid}/faab-market").json()["data"]
    assert body["failed_bids_capability"]["state"] == "not_on_platform"


def test_pre_faab_season_is_not_a_gap(client: TestClient):
    body = client.get(f"/v1/seasons/{KNOWN['season_id'][2016]}/faab-market").json()["data"]
    assert body["is_faab_era"] is False and body["teams"] == []


def test_faab_market_404(client: TestClient):
    assert client.get("/v1/seasons/99999/faab-market").status_code == 404


# --- trades ------------------------------------------------------------------------------


def test_trade_shows_every_asset_on_both_sides(mixed_era_db_path: Path, mixed_client: TestClient):
    sender, receiver = _trade_pair(mixed_era_db_path)
    for s in _session(mixed_era_db_path):
        (a,) = team_trades(s, sender)
        (b,) = team_trades(s, receiver)
    assert a["counterpart_team_id"] == receiver and b["counterpart_team_id"] == sender
    assert [p["season"] for p in a["picks_out"]] == [2027] and a["picks_in"] == []
    assert b["picks_in"] == a["picks_out"]
    assert a["faab_in"] == b["faab_out"] == 7.0
    assert {p["player_id"] for p in a["players_in"]} == {p["player_id"] for p in b["players_out"]}
    assert {p["player_id"] for p in a["players_out"]} == {p["player_id"] for p in b["players_in"]}
    assert len(a["players_in"]) + len(a["players_out"]) == 2
    body = mixed_client.get(f"/v1/teams/{sender}/transactions").json()["data"]
    (trade,) = body["trades"]
    assert trade["faab_in"] == 7.0 and trade["picks_out"][0]["round"] == 2


def test_team_failed_bids_and_capability(mixed_era_db_path: Path, mixed_client: TestClient, client):
    sid = _sid(mixed_era_db_path)
    ((loser,),) = _rows(
        mixed_era_db_path,
        "SELECT team_id FROM transactions WHERE season_id=? AND status='failed' AND "
        "effective_week=4 AND player_id=68",
        sid,
    )
    body = mixed_client.get(f"/v1/teams/{loser}/transactions").json()["data"]
    assert body["failed_bids_capability"]["state"] == "available"
    (lost,) = [f for f in body["failed_bids"] if f["week"] == 4 and f["player"]["player_id"] == 68]
    assert lost["bid"] == 4.0 and lost["winning_bid"] == 7.0 and lost["winner"]
    # failed claims never enter the flat feed (D3)
    assert all(t["status"] != "failed" for t in body["transactions"])
    legacy_team = KNOWN["team_id"][(2017, "ice")]
    legacy = client.get(f"/v1/teams/{legacy_team}/transactions").json()["data"]
    assert legacy["failed_bids"] == []
    assert legacy["failed_bids_capability"]["state"] == "not_on_platform"


# --- pick ledger -------------------------------------------------------------------------


def test_pick_ledger(mixed_era_db_path: Path, mixed_client: TestClient):
    for s in _session(mixed_era_db_path):
        ledger = league_pick_ledger(s)
    assert ledger["available"] is True
    (pick,) = ledger["picks"]
    assert (pick["pick_season"], pick["round"]) == (2027, 2)
    assert pick["original_owner"]["owner_name"] and pick["current_owner"]["owner_name"]
    assert pick["original_owner"] != pick["current_owner"]
    assert mixed_client.get("/v1/league/picks").json()["data"]["picks"][0]["round"] == 2


def test_pick_ledger_is_a_gap_without_a_sleeper_season(client: TestClient):
    body = client.get("/v1/league/picks").json()["data"]
    assert body == {"available": False, "reason": "traded_future_picks", "picks": []}
