"""Read-only audit of the committed NFL.com historical division artifact."""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import asdict
from typing import Any

import httpx
from bs4 import BeautifulSoup

from ff_dashboard.analytics.historical_divisions import historical_division_seasons

_DIVISION_RE = re.compile(r"Division\s+(\d+)\s*(?::\s*(.*))?$")
_RANK_RE = re.compile(r"(\d+)\s*\((\d+)\)")
_TEAM_ID_RE = re.compile(r"(?:teamId-|teamId=)(\d+)")


def _parse_page(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    divisions: list[dict[str, Any]] = []
    for wrap in soup.select("#leagueHistoryStandings .tableWrap.otherTableWrap.hasDivisions"):
        heading = wrap.find("h5")
        match = _DIVISION_RE.fullmatch(heading.get_text(" ", strip=True) if heading else "")
        if match is None:
            raise ValueError("NFL.com regular standings division heading changed")
        teams: list[dict[str, int]] = []
        for row in wrap.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            rank = _RANK_RE.match(cells[0].get_text(" ", strip=True))
            anchor = row.select_one("a.teamName")
            team_id = _TEAM_ID_RE.search(
                " ".join(anchor.get("class") or []) + " " + anchor.get("href", "") if anchor else ""
            )
            if rank is None or team_id is None:
                raise ValueError("NFL.com regular standings row shape changed")
            teams.append(
                {
                    "nfl_team_id": int(team_id.group(1)),
                    "final_division_rank": int(rank.group(1)),
                    "final_overall_regular_season_rank": int(rank.group(2)),
                }
            )
        divisions.append(
            {
                "division_number": int(match.group(1)),
                "name": match.group(2) or None,
                "teams": teams,
            }
        )
    return divisions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cookie-env",
        default="NFL_COOKIE",
        help="environment variable containing the authenticated NFL.com cookie",
    )
    args = parser.parse_args()
    cookie = os.environ.get(args.cookie_env, "").strip()
    if not cookie:
        parser.error(f"{args.cookie_env} is not set")

    failures = 0
    headers = {"Cookie": cookie, "User-Agent": "Mozilla/5.0"}
    with httpx.Client(headers=headers, follow_redirects=False, timeout=30) as client:
        for year, source in historical_division_seasons().items():
            response = client.get(source.source_url)
            response.raise_for_status()
            actual = _parse_page(response.text)
            expected = [
                {
                    **asdict(division),
                    "teams": [asdict(team) for team in division.teams],
                }
                for division in source.divisions
            ]
            if actual != expected:
                failures += 1
                print(f"{year}: artifact drift", file=sys.stderr)
            else:
                print(f"{year}: ok")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
