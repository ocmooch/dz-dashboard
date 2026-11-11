"""Legacy parity (Sleeper D0): nothing about the legacy seasons may change.

* **Fixture golden** (CI): every request of the matrix over the legacy fixture is stored under
  ``tests/golden/fixture/``. It must hold on the legacy-only fixture, and its *pinned* requests
  must still hold once a Sleeper 2026 season is loaded (the in-CI preview of the go-live).
* **Live golden** (local): ``scripts/snapshot_legacy_payloads.py --check`` against the frozen
  pre-go-live DB; skipped when that DB isn't on this machine.

Regenerate the fixture golden only for an *approved* intentional change:
``DZ_UPDATE_GOLDEN=1 uv run pytest tests/test_legacy_parity.py -k write_fixture_golden``.
Add goldens for new routes only (existing ones untouched): ``DZ_UPDATE_GOLDEN=new``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.golden_parity import (
    Req,
    build_matrix,
    canonical_sha,
    client_for,
    fetch,
    slug,
    strip_paths,
    subset_diffs,
    volatile_paths,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO / "tests" / "golden" / "fixture"
FIXTURE_MANIFEST = REPO / "tests" / "golden" / "fixture_manifest.json"
LIVE_MANIFEST = REPO / "tests" / "golden" / "live_manifest.json"
GOLDEN_DB = REPO / "data" / "golden" / "fantasy-golden-20261110.db"


def _manifest() -> list[dict[str, object]]:
    return json.loads(FIXTURE_MANIFEST.read_text())["requests"]


def _failures(client: TestClient, entries: list[dict[str, object]]) -> list[str]:
    out: list[str] = []
    for e in entries:
        url = str(e["url"])
        stored = json.loads((FIXTURE_DIR / slug(url)).read_text())
        assert canonical_sha(stored) == e["sha256"], f"golden file edited by hand: {url}"
        req = Req(url, bool(e["pinned"]), bool(e["binary"]))
        cur = strip_paths(fetch(client, req).to_json(), e["volatile"])  # type: ignore[arg-type]
        for d in subset_diffs(stored, cur):
            out.append(f"{url}  {d}")
    return out


@pytest.mark.skipif(not os.environ.get("DZ_UPDATE_GOLDEN"), reason="writer; set DZ_UPDATE_GOLDEN=1")
def test_write_fixture_golden(fixture_db_path: Path) -> None:
    only_new = os.environ["DZ_UPDATE_GOLDEN"] == "new"
    kept = _manifest() if only_new else []
    known = {str(e["url"]) for e in kept}
    reqs = [r for r in build_matrix(fixture_db_path) if r.url not in known]
    assets = fixture_db_path.parent / "assets"
    with client_for(fixture_db_path, assets) as c:
        first = {r.url: fetch(c, r).to_json() for r in reqs}
    with client_for(fixture_db_path, assets) as c:
        second = {r.url: fetch(c, r).to_json() for r in reqs}
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    if not only_new:
        for old in FIXTURE_DIR.glob("*.json"):
            old.unlink()
    entries: list[dict[str, object]] = list(kept)
    for r in reqs:
        vol = volatile_paths(first[r.url], second[r.url])
        payload = strip_paths(first[r.url], vol)
        (FIXTURE_DIR / slug(r.url)).write_text(json.dumps(payload, sort_keys=True, indent=1) + "\n")
        entries.append(
            {
                "url": r.url,
                "pinned": r.pinned,
                "binary": r.binary,
                "status": payload["status"],
                "sha256": canonical_sha(payload),
                "volatile": vol,
            }
        )
    FIXTURE_MANIFEST.write_text(json.dumps({"requests": entries}, indent=1) + "\n")


def test_fixture_golden_covers_every_v1_route() -> None:
    """Done-when: every `/v1` endpoint has golden coverage."""
    routes = set()
    for f in (REPO / "src" / "ff_dashboard" / "api").rglob("*.py"):
        routes |= set(re.findall(r'\.get\(\s*"(/v1/[^"]+)"', f.read_text()))
    pattern = {
        r: re.compile("^" + re.sub(r"\{[^}]+\}", r"[^/?]+", r) + r"(\?.*)?$") for r in routes
    }
    covered = {r for r, p in pattern.items() for e in _manifest() if p.match(str(e["url"]))}
    assert routes - covered == set()


def test_fixture_legacy_parity(fixture_db_path: Path) -> None:
    # Own client: the shared ``client`` fixture has no asset store, so avatars would 404.
    with client_for(fixture_db_path, fixture_db_path.parent / "assets") as c:
        assert _failures(c, _manifest()) == []


def test_fixture_parity_survives_a_sleeper_season(mixed_client: TestClient) -> None:
    """Pinned legacy answers must not move when a Sleeper season lands."""
    pinned = [e for e in _manifest() if e["pinned"]]
    assert pinned
    assert _failures(mixed_client, pinned) == []


@pytest.mark.skipif(
    not GOLDEN_DB.exists(), reason="frozen golden DB not on this machine (local only)"
)
def test_live_legacy_parity() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "snap", REPO / "scripts" / "snapshot_legacy_payloads.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.check() == 0


def test_live_manifest_is_committed_and_name_free() -> None:
    m = json.loads(LIVE_MANIFEST.read_text())
    assert len(m["requests"]) > 500
    assert all(e["url"].startswith("/v1/") for e in m["requests"])
    assert set(json.dumps(m)) <= set(map(chr, range(32, 127)))  # ids + hashes only


# --- the comparison itself -----------------------------------------------------------------


def test_subset_allows_new_keys_and_skips_volatile() -> None:
    golden = {"a": 1, "rows": [{"x": 1.5}]}
    assert (
        subset_diffs(golden, {"a": 1, "rows": [{"x": 1.5, "platform": "nfl_com"}], "new": 2}) == []
    )
    assert subset_diffs(golden, {"a": 2, "rows": [{"x": 1.5}]}) == [".a: 1 -> 2"]
    assert subset_diffs(golden, {"rows": [{"x": 1.5}]}) == [".a: missing"]
    assert subset_diffs(golden, {"a": 1, "rows": []}) == [".rows: list length 1 -> 0"]
    assert subset_diffs({"n": 1}, {"n": 1.0}) == [".n: 1 -> 1.0"]
    assert volatile_paths({"t": "10:00", "v": [1, 2]}, {"t": "10:01", "v": [1, 2]}) == [".t"]
    assert strip_paths({"t": 1, "k": {"t": 2}}, [".t"]) == {"k": {"t": 2}}


def test_failure_output_never_dumps_payloads() -> None:
    long_name = "x" * 200
    (diff,) = subset_diffs({"name": "a"}, {"name": long_name})
    assert len(diff) < 60


def test_snapshot_tooling_opens_no_writable_engine() -> None:
    for f in (
        REPO / "scripts" / "snapshot_legacy_payloads.py",
        REPO / "tests" / "golden_parity.py",
    ):
        src = f.read_text()
        assert "create_engine(" not in src and "_create_writer" not in src, f.name
