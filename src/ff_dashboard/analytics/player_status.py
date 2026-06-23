"""Classify NFL.com roster ``player_status`` against evidence the player played.

NFL.com's historical game-center pages stamp each player's *current* roster
status onto past weeks — a current-state drift (see ``roster_snapshots`` for the
sibling case). So a player who demonstrably played and scored in week N can carry
an "Inactive" / "Injured Reserve" / "Suspended" badge that is simply *today's*
status, not week N's. Showing a did-not-play badge on a player who played is the
contradiction this module exists to suppress.

The rule (per the league owner): a player who **played** — has a real stat line
or a score that week, an organic 0 included — must never show an *availability /
roster* status (IA, IR, SUS, NA, PUP, NFI, OUT, DNP, BYE …). Game-time
**injury-report designations** (Questionable / Doubtful / Probable) are
compatible with playing and are kept.

Only the small, well-defined set of game-time designations is treated as
compatible; every other status is incompatible-with-play. So an unfamiliar
status on a player we can *prove* played is suppressed rather than shown — the
honest asymmetry: a missed-but-real designation merely drops a badge, whereas a
wrong "Inactive" on a 22-point line is exactly the failure we are fixing.
"""

from __future__ import annotations

# Game-time injury-report designations: compatible with actually playing. Stored
# as both the NFL.com short codes and their expanded labels, since either form
# may reach us (``player_status`` is the code, ``player_status_label`` the label).
_COMPATIBLE_WITH_PLAY = frozenset(
    {
        "Q",
        "QUESTIONABLE",
        "D",
        "DOUBTFUL",
        "P",
        "PROBABLE",
    }
)


def _normalize(status: str | None) -> str | None:
    if not status:
        return None
    cleaned = status.strip().upper()
    return cleaned or None


def is_compatible_with_play(status: str | None) -> bool:
    """True when *status* can truthfully coexist with the player having played.

    Game-time injury designations (Q/D/P) are compatible; a missing status is
    treated as compatible (there is nothing to suppress). Every other status —
    every availability / roster status — is incompatible.
    """
    normalized = _normalize(status)
    if normalized is None:
        return True
    return normalized in _COMPATIBLE_WITH_PLAY


def should_suppress_status(status: str | None, *, played: bool) -> bool:
    """True when *status* must not be surfaced because the player played.

    Only suppresses when there is positive evidence the player played AND the
    status is incompatible with playing. A compatible designation, or a player
    who did not play, is never suppressed.
    """
    if not played:
        return False
    return not is_compatible_with_play(status)
