"""Live legacy golden snapshots (Sleeper D0). Read-only against a frozen DB copy.

    uv run python scripts/snapshot_legacy_payloads.py --freeze <upstream backup.db>
    uv run python scripts/snapshot_legacy_payloads.py --write    # golden JSON + manifest
    uv run python scripts/snapshot_legacy_payloads.py --check    # re-run and diff (golden ⊆ current)

The golden DB and JSON live under ``data/golden/`` (gitignored: they hold real names). Only
``tests/golden/live_manifest.json`` (request list, hashes, volatile paths; ids, no names) is
committed. Plan: ``docs/plans/sleeper-d0-golden-snapshots.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tests.golden_parity import (  # noqa: E402
    LIVE_YEARS,
    Response,
    build_matrix,
    canonical_sha,
    client_for,
    fetch,
    slug,
    strip_paths,
    subset_diffs,
    volatile_paths,
)

GOLDEN_DB = REPO / "data" / "golden" / "fantasy-golden-20261110.db"
LIVE_DIR = REPO / "data" / "golden" / "live"
MANIFEST = REPO / "tests" / "golden" / "live_manifest.json"
ASSETS_ROOT = (REPO.parent / "danger-zone" / "data" / "assets").resolve()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def freeze(src: Path) -> None:
    if GOLDEN_DB.exists():
        sys.exit(f"{GOLDEN_DB} already exists; refusing to overwrite the frozen baseline")
    GOLDEN_DB.parent.mkdir(parents=True, exist_ok=True)
    tmp = GOLDEN_DB.with_suffix(".partial")
    # immutable=1: no locks, no -wal/-shm files beside the source backup (mode=ro would add them).
    s = sqlite3.connect(f"file:{src}?immutable=1", uri=True)
    d = sqlite3.connect(tmp)
    try:
        s.backup(d)
        d.execute("PRAGMA journal_mode=DELETE")
        ok = d.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        d.close()
        s.close()
    if ok != "ok":
        tmp.unlink()
        sys.exit(f"integrity_check failed on the copy: {ok}")
    tmp.rename(GOLDEN_DB)
    GOLDEN_DB.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    print(f"frozen {GOLDEN_DB.name}  sha256={file_sha(GOLDEN_DB)}  from {src.name}")


def _run(reqs: list, db: Path) -> dict[str, Response]:
    with client_for(db, ASSETS_ROOT) as c:
        return {r.url: fetch(c, r) for r in reqs}


def write() -> None:
    if not GOLDEN_DB.exists():
        sys.exit("no golden DB; run --freeze first")
    reqs = build_matrix(GOLDEN_DB, LIVE_YEARS)
    t = time.monotonic()
    first = _run(reqs, GOLDEN_DB)
    second = _run(reqs, GOLDEN_DB)
    print(f"{len(reqs)} requests x2 in {time.monotonic() - t:.0f}s")
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    for old in LIVE_DIR.glob("*.json"):
        old.unlink()
    entries = []
    for r in reqs:
        a, b = first[r.url].to_json(), second[r.url].to_json()
        vol = volatile_paths(a, b)
        payload = strip_paths(a, vol)
        (LIVE_DIR / slug(r.url)).write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        entries.append(
            {
                "url": r.url,
                "pinned": r.pinned,
                "binary": r.binary,
                "status": a["status"],
                "sha256": canonical_sha(payload),
                "volatile": vol,
            }
        )
    conn = sqlite3.connect(f"file:{GOLDEN_DB}?mode=ro", uri=True)
    try:
        rev = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        conn.close()
    manifest = {
        "golden_db": GOLDEN_DB.name,
        "golden_db_sha256": file_sha(GOLDEN_DB),
        "source": "danger-zone data/backups/fantasy-pre-guard-v2-20261110T140400Z.db (pre-go-live)",
        "upstream_revision": rev,
        "years": list(LIVE_YEARS),
        "compare": "golden subset of current; new keys allowed; volatile paths skipped",
        "requests": entries,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
    statuses: dict[int, int] = {}
    for e in entries:
        statuses[e["status"]] = statuses.get(e["status"], 0) + 1
    vol_n = sum(1 for e in entries if e["volatile"])
    print(f"wrote {len(entries)} snapshots; statuses {statuses}; {vol_n} with volatile paths")


def check(db: Path | None = None) -> int:
    """Return the number of failing requests (0 = parity holds)."""
    db = db or GOLDEN_DB
    manifest = json.loads(MANIFEST.read_text())
    if file_sha(db) != manifest["golden_db_sha256"]:
        sys.exit("golden DB sha256 differs from the manifest; refusing to compare")
    from tests.golden_parity import Req

    reqs = [Req(e["url"], e["pinned"], e["binary"]) for e in manifest["requests"]]
    current = _run(reqs, db)
    failures = 0
    for e in manifest["requests"]:
        stored_path = LIVE_DIR / slug(e["url"])
        stored = json.loads(stored_path.read_text())
        if canonical_sha(stored) != e["sha256"]:
            print(f"TAMPERED {e['url']}: stored golden JSON no longer matches the manifest hash")
            failures += 1
            continue
        cur = strip_paths(current[e["url"]].to_json(), e["volatile"])
        diffs = subset_diffs(stored, cur)
        if diffs:
            failures += 1
            print(f"DIFF {e['url']}")
            for d in diffs:
                print(f"   {d}")
    print(f"{len(reqs)} requests, {failures} failing")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--freeze", type=Path, metavar="BACKUP_DB")
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    if a.freeze:
        freeze(a.freeze.resolve())
        return 0
    if a.write:
        write()
        return 0
    return 1 if check() else 0


if __name__ == "__main__":
    raise SystemExit(main())
