"""Commissioner history analytics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ff_pipeline.repository.queries import commissioner_terms
from sqlalchemy import select

from ff_dashboard.analytics.common import require_league

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class CommissionerTerm:
    owner_id: int
    owner_name: str
    from_year: int
    to_year: int | None
    seasons: int
    notes: str | None


def commissioner_history(session: Session) -> list[CommissionerTerm]:
    """Return all commissioner terms, oldest first."""
    league = require_league(session)
    terms = commissioner_terms(session, league.league_id)

    result: list[CommissionerTerm] = []
    for term in terms:
        owner_name = term.owner.display_name or str(term.owner_id)
        from_year = int(term.from_year)
        to_year = int(term.to_year) if term.to_year is not None else None
        if to_year is not None:
            seasons = to_year - from_year + 1
        else:
            from ff_pipeline.repository.models import Season
            latest = session.execute(
                select(Season.year)
                .where(Season.league_id == league.league_id)
                .order_by(Season.year.desc())
                .limit(1)
            ).scalar()
            seasons = (int(latest) - from_year + 1) if latest else 1
        result.append(
            CommissionerTerm(
                owner_id=int(term.owner_id),
                owner_name=owner_name,
                from_year=from_year,
                to_year=to_year,
                seasons=seasons,
                notes=term.notes,
            )
        )
    return result


def commissioner_for_year(terms: list[CommissionerTerm], year: int) -> CommissionerTerm | None:
    """Return the commissioner term that covers a given season year, or None."""
    for t in terms:
        end = t.to_year if t.to_year is not None else 9999
        if t.from_year <= year <= end:
            return t
    return None
