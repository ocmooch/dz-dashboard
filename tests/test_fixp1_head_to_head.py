"""fix-P1 / F-12 + F-23 — head-to-head cumulative margin + closest meeting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ff_dashboard.analytics.head_to_head import pairwise_record
from tests.conftest import KNOWN

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def test_cumulative_margin_and_closest_meeting(session: Session) -> None:
    mav, ice = KNOWN["owner_id"]["mav"], KNOWN["owner_id"]["ice"]
    h2h = pairwise_record(session, mav, ice)
    # Meetings (Maverick view): 2015 +10, 2016 +70, 2017 -5 → cumulative +75.
    assert h2h["cumulative_margin_for_a"] == 75.0
    # Closest meeting is the 5-pt 2017 wk2 game (Maverick lost by 5).
    assert h2h["closest_meeting"]["margin_for_a"] == -5.0
    assert h2h["closest_meeting"]["season_year"] == 2017
    assert h2h["closest_meeting"]["week"] == 2
    assert h2h["closest_meeting"]["matchup_id"] is not None


def test_orientation_is_signed_mirror(session: Session) -> None:
    mav, ice = KNOWN["owner_id"]["mav"], KNOWN["owner_id"]["ice"]
    ab = pairwise_record(session, mav, ice)
    ba = pairwise_record(session, ice, mav)
    assert ba["cumulative_margin_for_a"] == -ab["cumulative_margin_for_a"]
    assert ba["closest_meeting"]["margin_for_a"] == -ab["closest_meeting"]["margin_for_a"]


def test_meetings_list_is_chronological_and_oriented(session: Session) -> None:
    mav, ice = KNOWN["owner_id"]["mav"], KNOWN["owner_id"]["ice"]
    meetings = pairwise_record(session, mav, ice)["meetings"]
    # Three regular-season meetings, oldest → newest, oriented to Maverick.
    assert [m["season_year"] for m in meetings] == [2015, 2016, 2017]
    assert [m["margin_for_a"] for m in meetings] == [10.0, 70.0, -5.0]
    # Each meeting carries both scores and a deep-link.
    assert meetings[0]["a_score"] == 110.0
    assert meetings[0]["b_score"] == 100.0
    assert all(m["matchup_id"] is not None for m in meetings)
    # Flipping the orientation mirrors every signed margin.
    ba = pairwise_record(session, ice, mav)["meetings"]
    assert [m["margin_for_a"] for m in ba] == [-10.0, -70.0, 5.0]


def test_no_meetings_omits_new_fields_gracefully(session: Session) -> None:
    # Slider (2015-16) and Viper (2017) never overlapped.
    slider, viper = KNOWN["owner_id"]["slider"], KNOWN["owner_id"]["viper"]
    h2h = pairwise_record(session, slider, viper)
    assert h2h["available"] is False
    assert "cumulative_margin_for_a" not in h2h
    assert "closest_meeting" not in h2h
