"""Sleeper D1: provenance + capabilities in the contract (plan sleeper-d1-provenance-capabilities)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.orm import Session

from ff_dashboard.analytics import platform
from ff_dashboard.engine import create_readonly_engine
from tests.sleeper_fixture import SLEEPER_YEAR

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from fastapi.testclient import TestClient

STATES = {"available", "partial", "derived", "not_yet", "not_on_platform", "not_used"}


@pytest.fixture
def mixed_session(mixed_era_db_path: Path) -> Iterator[Session]:
    eng = create_readonly_engine(f"sqlite:///{mixed_era_db_path}")
    with Session(eng) as s:
        yield s
    eng.dispose()


def _data(client: TestClient, url: str) -> Any:
    r = client.get(url)
    assert r.status_code == 200, url
    return r.json()["data"]


# --- analytics/platform.py ------------------------------------------------------------------


def test_capability_states_resolve_and_not_used_is_silent(mixed_session: Session) -> None:
    seen: set[str] = set()
    for sid in (1, 5):  # legacy 2015 + Sleeper 2026 in the mixed fixture
        for key, cap in platform.season_capabilities(mixed_session, sid).items():
            assert cap["state"] in STATES, key
            seen.add(cap["state"])
            if cap["state"] == "not_used":
                assert cap["note"] is None, key
    assert {"available", "not_on_platform"} <= seen


def test_platform_eras_cover_every_season_with_a_platform(
    session: Session, mixed_session: Session
) -> None:
    assert platform.platform_eras(session) == [
        {"platform": "nfl_com", "label": "NFL.com", "start_year": 2015, "end_year": None}
    ]
    assert platform.platform_eras(mixed_session) == [
        {"platform": "nfl_com", "label": "NFL.com", "start_year": 2015, "end_year": 2018},
        {"platform": "sleeper", "label": "Sleeper", "start_year": SLEEPER_YEAR, "end_year": None},
    ]


def test_current_season_is_the_in_progress_sleeper_season(mixed_session: Session) -> None:
    cur = platform.current_season(mixed_session)
    assert cur["current_season_id"] == 5
    assert isinstance(cur["current_week"], int)


# --- contract -------------------------------------------------------------------------------


def test_season_level_payloads_carry_platform_and_capabilities(mixed_client: TestClient) -> None:
    seasons = _data(mixed_client, "/v1/seasons")["seasons"]
    assert seasons
    for s in seasons:
        assert s["platform"] in {"nfl_com", "sleeper"}
        assert s["platform_label"] in {"NFL.com", "Sleeper"}
        assert s["capabilities"]["standings"]["state"] in STATES
    summary = _data(mixed_client, f"/v1/seasons/{seasons[0]['season_id']}")
    assert summary["platform"] and summary["capabilities"]
    for row in _data(mixed_client, "/v1/league/timeline")["seasons"]:
        assert row["platform"] and row["capabilities"]


def test_meta_carries_platform_eras_and_current_season(mixed_client: TestClient) -> None:
    meta = _data(mixed_client, "/v1/meta")
    assert [e["platform"] for e in meta["platform_eras"]] == ["nfl_com", "sleeper"]
    assert meta["current_season_id"] == 5
    cov = _data(mixed_client, "/v1/meta/coverage")
    assert cov["season_platforms"][str(SLEEPER_YEAR)] == "sleeper"
    assert cov["capabilities"][str(SLEEPER_YEAR)]["standings"]["state"] in STATES


def test_timeline_shows_the_move_to_sleeper_once(mixed_client: TestClient) -> None:
    changes = _data(mixed_client, "/v1/league/eras")["changes"]
    moved = [c for c in changes if c["platform_changed"]]
    assert len(moved) == 1
    assert moved[0]["season_year"] == SLEEPER_YEAR
    (detail,) = [d for d in moved[0]["details"] if d["category"] == "platform"]
    assert detail["title"] == "Moved to Sleeper"
    assert (detail["before"], detail["after"]) == ("NFL.com", "Sleeper")


def test_legacy_only_league_has_no_platform_change(client: TestClient) -> None:
    assert not any(c["platform_changed"] for c in _data(client, "/v1/league/eras")["changes"])


def test_capability_matrix_for_about(mixed_client: TestClient) -> None:
    m = _data(mixed_client, "/v1/meta/capabilities")
    assert "standings" in m["keys"]
    years = [s["season_year"] for s in m["seasons"]]
    assert years == sorted(years) and SLEEPER_YEAR in years
    for s in m["seasons"]:
        assert set(s["cells"]) == set(m["keys"])


def test_platform_accounts_carry_no_usernames_or_ids(mixed_client: TestClient) -> None:
    managers = _data(mixed_client, "/v1/league/managers")["managers"]
    accounts = [a for m in managers for a in m["platform_accounts"]]
    assert accounts
    for a in accounts:
        assert set(a) == {"platform", "label", "first_season", "last_season"}


def test_platform_literal_guard_passes_on_the_tree_and_catches_a_plant(tmp_path: Path) -> None:
    import subprocess
    from pathlib import Path as P

    script = P(__file__).resolve().parents[1] / "scripts" / "check_platform_literals.sh"
    assert subprocess.run([str(script)], capture_output=True, check=False).returncode == 0
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "platform.ts").write_text('const ok = "sleeper";\n')
    (tmp_path / "Page.tsx").write_text('if (season.platform === "sleeper") {}\n')
    (tmp_path / "Page.test.tsx").write_text('const mock = { platform: "sleeper" };\n')
    bad = subprocess.run([str(script), str(tmp_path)], capture_output=True, text=True, check=False)
    assert bad.returncode == 1
    assert "/Page.tsx:1:" in bad.stdout
    assert "/lib/platform.ts:" not in bad.stdout and "/Page.test.tsx:" not in bad.stdout
