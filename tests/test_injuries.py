"""Unit tests for the injury-report presentation normalizer.

Pure functions over constructed ``PlayerInjuryReport`` rows — no DB. Guards the
"what counts as a real designation / body part / practice code" rules that both
the box score and the team roster depend on (`analytics/injuries.py`).
"""

from __future__ import annotations

from ff_pipeline.repository.models import PlayerInjuryReport

from ff_dashboard.analytics.injuries import injury_fields


def _report(**kwargs: object) -> PlayerInjuryReport:
    report = PlayerInjuryReport()
    for key, value in kwargs.items():
        setattr(report, key, value)
    return report


def test_none_report_is_all_null() -> None:
    assert injury_fields(None) == {
        "injury_status": None,
        "injury_body_part": None,
        "injury_secondary": None,
        "injury_practice_status": None,
    }


def test_full_designation_with_secondary_and_practice() -> None:
    fields = injury_fields(
        _report(
            report_status="Out",
            report_primary_injury="Hamstring",
            report_secondary_injury="Back",
            practice_status="Did Not Participate In Practice",
        )
    )
    assert fields == {
        "injury_status": "Out",
        "injury_body_part": "Hamstring",
        "injury_secondary": "Back",
        "injury_practice_status": "DNP",
    }


def test_practice_codes_map_to_short_form() -> None:
    cases = {
        "Limited Participation in Practice": "Ltd",
        "Full Participation in Practice": "Full",
        "Out (Definitely Will Not Play)": "Out",
    }
    for raw, short in cases.items():
        fields = injury_fields(_report(report_status="Questionable", practice_status=raw))
        assert fields["injury_practice_status"] == short


def test_blank_status_collapses_to_none_so_no_badge() -> None:
    # A practice-only row (no game designation) must not produce a badge: the
    # frontend gates on injury_status, so it stays null even with practice info.
    fields = injury_fields(
        _report(
            report_status="",
            report_primary_injury="Ankle",
            practice_status="Full Participation in Practice",
        )
    )
    assert fields["injury_status"] is None
    assert fields["injury_practice_status"] == "Full"


def test_unknown_status_text_is_not_a_designation() -> None:
    # nflverse emits the odd free-text "Note"; it is not a game status.
    assert injury_fields(_report(report_status="Note"))["injury_status"] is None


def test_probable_is_kept_for_pre_2016_honesty() -> None:
    # "Probable" was a real designation the NFL retired after 2015.
    assert injury_fields(_report(report_status="Probable"))["injury_status"] == "Probable"


def test_non_injury_secondary_note_is_dropped() -> None:
    fields = injury_fields(
        _report(
            report_status="Out",
            report_primary_injury="Heel",
            report_secondary_injury="Not injury related - personal matter",
        )
    )
    assert fields["injury_body_part"] == "Heel"
    assert fields["injury_secondary"] is None


def test_non_injury_note_in_primary_is_dropped() -> None:
    # Load-management ("resting player") lands in the primary field; it should
    # not masquerade as a body part, leaving just the (real) game designation.
    fields = injury_fields(
        _report(
            report_status="Questionable",
            report_primary_injury="Not injury related - resting player",
        )
    )
    assert fields["injury_status"] == "Questionable"
    assert fields["injury_body_part"] is None


def test_whitespace_only_fields_are_treated_as_missing() -> None:
    fields = injury_fields(
        _report(
            report_status="Questionable",
            report_primary_injury="   ",
            report_secondary_injury="  ",
            practice_status="   ",
        )
    )
    assert fields["injury_body_part"] is None
    assert fields["injury_secondary"] is None
    assert fields["injury_practice_status"] is None
