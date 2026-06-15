"""CI guardrail for the zero-score / DST drift audit.

This is the deliberately *top-level* double-check for the matchup zero-status /
DST drift work (merged in PR #67). It runs the same read-only audit as
``scripts/audit_zero_score_gaps.py`` against the fixture DB inside the normal
pytest gate, so a regression that reintroduces an unexpected NFL.com-0 /
nflverse-nonzero row — or silently collapses the missing-DST gap into a fake
zero — fails CI without re-running the deep scoring reconstruction each time.

The real-DB sweep stays a local command (the script's ``main``); CI only needs
this fast structural tripwire over the fixture.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_zero_score_gaps.py"


def _load_audit() -> Callable[..., dict[str, Any]]:
    spec = importlib.util.spec_from_file_location("audit_zero_score_gaps", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast("Callable[..., dict[str, Any]]", module.audit)


# The fixture DB deliberately seeds one representative row per drift class so the
# audit exercises every classification path. We assert each path stays *alive*
# rather than locking exact counts (robust to fixture growth, sensitive to a path
# silently collapsing). On the real DB the invariant is the opposite — zero
# unexpected/missing rows — which stays the local ``audit_zero_score_gaps`` run.
_EXPECTED_DRIFT_PATHS = (
    "non_zero_scored",  # ordinary scored points still flow through
    "bye_zero",  # opponent "Bye" -> status label, not a bare 0
    "did_not_play_missing_row",  # scored-season absence -> DNP, not a gap
    "unexpected_zero",  # league 0 + nflverse material pts -> flagged, not silent
    "missing_dst",  # missing D/ST row -> gap preserved, never a fake 0
    "unscored_season_rows",  # whole unscored season -> page gap, not zeros
)


def test_fixture_audit_keeps_every_drift_path_alive(session: Session) -> None:
    result = _load_audit()(session, example_limit=5)
    counts = result["counts"]

    # Guard against a vacuous tripwire: the fixture must actually scope rows.
    assert result["total_rows"] > 0

    missing = [path for path in _EXPECTED_DRIFT_PATHS if counts.get(path, 0) < 1]
    assert not missing, (
        f"drift-handling path(s) no longer exercised by the audit: {missing}; "
        f"counts={counts}"
    )
