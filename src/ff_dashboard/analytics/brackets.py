"""Official postseason brackets (Sleeper D5).

A Sleeper season stores its real brackets in ``playoff_brackets`` (upstream S7), so the dashboard
shows those instead of deriving one from who played whom. A season without bracket rows (every
NFL.com season) keeps :func:`bracket.season_bracket`, marked ``source="derived"``.

Upstream conventions this module follows (``docs/sleeper/00_UPSTREAM_STATE.md`` §4):

* ``placement`` is Sleeper's bracket-relative ``p``. Absolute place = offset + p for the winner
  and offset + p + 1 for the loser, where the losers bracket's offset is the winners bracket size;
* every bracket game is a playoff game; losers-bracket games are also consolation;
* the champion / runner-up / last place are on ``seasons`` once the deciding week is final.

An unfinished week is unscored (D3): its game shows the pairing, no scores and no winner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ff_pipeline.repository import queries
from ff_pipeline.repository.models import Matchup
from ff_pipeline.repository.queries import get_season, get_team
from sqlalchemy import select

from ff_dashboard.analytics import game_state
from ff_dashboard.analytics.bracket import (
    CHAMPIONSHIP_GAME_LABEL,
    TIER_CHAMPIONSHIP,
    TIER_CONSOLATION,
    TIER_PLAYOFF,
    TOILET_BOWL_GAME_LABEL,
    _team_ref,
    season_bracket,
)
from ff_dashboard.analytics.common import owner_name_map, regular_season_weeks, require_league
from ff_dashboard.analytics.conferences import conference_map
from ff_dashboard.analytics.platform import AVAILABLE, season_capabilities

if TYPE_CHECKING:
    from ff_pipeline.repository.models import PlayoffBracket, Season
    from sqlalchemy.orm import Session

OFFICIAL_CAVEAT = "The league's official playoff brackets, as recorded by the platform."
SOURCE_OFFICIAL = "official"
SOURCE_DERIVED = "derived"
WINNERS = "winners"
LOSERS = "losers"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def place_label(place: int | None) -> str | None:
    """The legacy game-label vocabulary for a placement game ("Championship", "3rd Place", …)."""
    if place is None:
        return None
    return CHAMPIONSHIP_GAME_LABEL if place == 1 else f"{_ordinal(place)} Place"


def _winners_size(rows: list[PlayoffBracket]) -> int:
    seeded = {t for r in rows if r.bracket == WINNERS for t in (r.team1_id, r.team2_id) if t}
    return len(seeded)


def absolute_place(row: PlayoffBracket, winners_size: int) -> int | None:
    """The place the winner of ``row`` takes (its loser takes the next one); ``None`` if unplaced."""
    if row.placement is None:
        return None
    return (0 if row.bracket == WINNERS else winners_size) + int(row.placement)


def _toilet_row(rows: list[PlayoffBracket]) -> PlayoffBracket | None:
    """The losers-bracket game for the last places: the one with the highest placement."""
    placed = [r for r in rows if r.bracket == LOSERS and r.placement is not None]
    return max(placed, key=lambda r: int(r.placement or 0)) if placed else None


def _bracket_matchups(
    session: Session, season_id: int, regular_weeks: int
) -> dict[tuple[int, frozenset[int]], list[Matchup]]:
    """Postseason game rows by (week, team pair). Idle bye/placed rows are not games."""
    out: dict[tuple[int, frozenset[int]], list[Matchup]] = {}
    for m in session.scalars(
        select(Matchup).where(Matchup.season_id == season_id, Matchup.week > regular_weeks)
    ):
        if m.opponent_team_id is not None:  # game_state.is_game: idle bye/placed rows have none
            key = (int(m.week), frozenset({int(m.team_id), int(m.opponent_team_id)}))
            out.setdefault(key, []).append(m)
    return out


def _resolve(
    row: PlayoffBracket,
    regular_weeks: int,
    games: dict[tuple[int, frozenset[int]], list[Matchup]],
) -> dict[str, Any]:
    """One bracket row joined to its matchup rows: week, matchup ids, scores, pending, winner."""
    week = regular_weeks + int(row.round)
    t1, t2 = row.team1_id, row.team2_id
    ms = games.get((week, frozenset({t1, t2}))) if t1 and t2 else None
    ms = ms or []
    pending = any(game_state.is_pending(m) for m in ms)
    scores: dict[int, float | None] = {}
    if not pending:
        for m in ms:
            scores[int(m.team_id)] = m.team_score
    # A bracket winner shows once its week is final (a pending week is never a result).
    winner = None if pending else row.winner_team_id
    return {
        "week": week,
        "matchup_ids": sorted(int(m.matchup_id) for m in ms),
        "pending": pending,
        "scores": scores,
        "winner": int(winner) if winner is not None else None,
        "loser": int(row.loser_team_id) if row.loser_team_id is not None and winner else None,
    }


def _section(
    rows: list[PlayoffBracket],
    bracket: str,
    resolved: dict[int, dict[str, Any]],
    winners_size: int,
    ref: Any,
) -> dict[str, Any]:
    mine = [r for r in rows if r.bracket == bracket]
    if not mine:
        return {"size": 0, "rounds": [], "bye_teams": []}
    n_rounds = max(int(r.round) for r in mine)
    round1 = {t for r in mine if r.round == 1 for t in (r.team1_id, r.team2_id) if t}
    later = {t for r in mine if r.round > 1 for t in (r.team1_id, r.team2_id) if t}
    byes = [ref(t, None, False) for t in sorted(later - round1)]
    bye_teams = [
        {k: b[k] for k in ("team_id", "team_name", "owner_id", "owner_name", "conference_name")}
        for b in byes
        if b is not None
    ]
    rounds: list[dict[str, Any]] = []
    for rnum in range(1, n_rounds + 1):
        games: list[dict[str, Any]] = []
        for r in (x for x in mine if x.round == rnum):
            g = resolved[int(r.bracket_id)]
            place = absolute_place(r, winners_size)
            games.append(
                {
                    "week": g["week"],
                    "matchup_id": g["matchup_ids"][0] if g["matchup_ids"] else None,
                    "is_playoff": True,
                    "is_consolation": bracket == LOSERS,
                    "game_label": place_label(place),
                    "placement": place,
                    "week_pending": g["pending"],
                    "team_a": ref(
                        r.team1_id, g["scores"].get(r.team1_id), g["winner"] == r.team1_id
                    ),
                    "team_b": ref(
                        r.team2_id, g["scores"].get(r.team2_id), g["winner"] == r.team2_id
                    ),
                    "winner_team_id": g["winner"],
                }
            )
        if rnum == n_rounds:
            label = "Finals"
        elif rnum == n_rounds - 1:
            label = "Semifinals"
        elif rnum == 1:
            label = "First Round"
        else:
            label = f"Round {rnum}"
        rounds.append(
            {
                "round_num": rnum,
                "round_label": label,
                "bye_teams": bye_teams if rnum == 1 else [],
                "games": games,
            }
        )
    size = len(round1 | later)
    return {"size": size, "rounds": rounds, "bye_teams": bye_teams}


def _context(
    session: Session, season: Season
) -> tuple[list[PlayoffBracket], int, int, dict[int, dict[str, Any]]] | None:
    rows = queries.brackets_for_season(session, season.season_id)
    if not rows:
        return None
    regular_weeks = regular_season_weeks(session, season)
    games = _bracket_matchups(session, season.season_id, regular_weeks)
    resolved = {int(r.bracket_id): _resolve(r, regular_weeks, games) for r in rows}
    return rows, regular_weeks, _winners_size(rows), resolved


def official_bracket(session: Session, season_id: int) -> dict[str, Any] | None:
    """The season's official brackets in the shared ``SeasonBracket`` shape; ``None`` if absent."""
    require_league(session)
    season = get_season(session, season_id)
    if season is None:
        return None
    ctx = _context(session, season)
    if ctx is None:
        return None
    rows, regular_weeks, winners_size, resolved = ctx

    owners = owner_name_map(session)
    conf = conference_map(session, season_id)
    cache: dict[int, Any] = {}

    def ref(team_id: int | None, score: float | None, is_winner: bool) -> dict[str, Any] | None:
        return _team_ref(team_id, score, is_winner, cache, owners, session, conf)

    playoff = _section(rows, WINNERS, resolved, winners_size, ref)
    consolation = _section(rows, LOSERS, resolved, winners_size, ref)

    sacko = official_sacko(session, season_id)
    if sacko is not None and sacko["matchup_id"] is not None:
        for rnd in consolation["rounds"]:
            for g in rnd["games"]:
                if g["matchup_id"] != sacko["matchup_id"]:
                    continue
                for side in ("team_a", "team_b"):
                    if g[side] is not None and g[side]["team_id"] == sacko["team_id"]:
                        g[side]["is_sacko"] = True

    return {
        "season_id": season_id,
        "season_year": season.year,
        "regular_season_weeks": regular_weeks,
        "caveat": OFFICIAL_CAVEAT,
        "available": True,
        "reason": None,
        "source": SOURCE_OFFICIAL,
        # Seeds and pairings are current state until every game is decided (00 §3).
        "is_provisional": any(g["winner"] is None for g in resolved.values()),
        "consolation_distinguished": True,
        "playoff_bracket": playoff,
        "consolation_bracket": consolation,
    }


def official_sacko(session: Session, season_id: int) -> dict[str, Any] | None:
    """The recorded last-place team of a season with official brackets, tied to its game.

    ``None`` until upstream records last place (the deciding week is final), and never derived
    from an undecided bracket."""
    season = get_season(session, season_id)
    if season is None or season.last_place_team_id is None:
        return None
    ctx = _context(session, season)
    if ctx is None:
        return None
    rows, _, _, resolved = ctx
    lp = int(season.last_place_team_id)
    toilet = _toilet_row(rows)
    matchup_id = None
    if toilet is not None:
        g = resolved[int(toilet.bracket_id)]
        if g["loser"] == lp and g["matchup_ids"]:
            matchup_id = g["matchup_ids"][0]
    team = get_team(session, lp)
    return {
        "team_id": lp,
        "owner_id": team.owner_id if team is not None else None,
        "matchup_id": matchup_id,
        "season_year": season.year,
        "source": SOURCE_OFFICIAL,
    }


def official_classification(session: Session, season: Season) -> dict[str, Any] | None:
    """:func:`bracket.postseason_classification` from official brackets; ``None`` if absent."""
    ctx = _context(session, season)
    if ctx is None:
        return None
    rows, _, winners_size, resolved = ctx
    toilet = _toilet_row(rows)
    by_matchup_id: dict[int, dict[str, Any]] = {}
    championship_matchup_id: int | None = None
    for r in rows:
        g = resolved[int(r.bracket_id)]
        place = absolute_place(r, winners_size)
        if r.bracket == WINNERS and place == 1:
            tier, label = TIER_CHAMPIONSHIP, CHAMPIONSHIP_GAME_LABEL
            if g["matchup_ids"]:
                championship_matchup_id = g["matchup_ids"][0]
        elif r.bracket == WINNERS:
            tier, label = TIER_PLAYOFF, None
        else:
            tier = TIER_CONSOLATION
            label = TOILET_BOWL_GAME_LABEL if toilet is not None and r is toilet else None
        for mid in g["matchup_ids"]:
            by_matchup_id[mid] = {"tier": tier, "game_label": label}
    return {
        "season_id": season.season_id,
        "season_year": season.year,
        "consolation_distinguished": True,
        "by_matchup_id": by_matchup_id,
        "championship_matchup_id": championship_matchup_id,
        "sacko": official_sacko(session, season.season_id),
    }


def season_brackets(session: Session, season_id: int) -> dict[str, Any] | None:
    """Official brackets where the platform recorded them, else today's derived bracket."""
    if get_season(session, season_id) is None:
        return None
    caps = season_capabilities(session, season_id)
    if (caps.get("official_brackets") or {}).get("state") == AVAILABLE:
        official = official_bracket(session, season_id)
        if official is not None:
            return official
    derived = season_bracket(session, season_id)
    if derived is None:
        return None
    return {**derived, "source": SOURCE_DERIVED, "is_provisional": False}
