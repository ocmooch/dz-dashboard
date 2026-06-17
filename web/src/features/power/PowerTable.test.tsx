import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PowerTable } from "./PowerTable";
import type { PowerRanking } from "./usePower";

const row = (rank: number, owner: string, power: number, delta: number, standingsRank: number) => ({
  rank,
  team_id: rank,
  team_name: `${owner} 2017`,
  owner_id: rank,
  owner_name: owner,
  wins: 2,
  losses: 0,
  ties: 0,
  points_for: 260,
  power_score: power,
  points_for_per_game: 130,
  all_play_win_pct: 0.75,
  win_pct: 1,
  recent_points_for_per_game: 130,
  z_points_for: 1.2,
  z_all_play_win_pct: 1.0,
  z_win_pct: 1.0,
  z_recent: 1.1,
  standings_rank: standingsRank,
  rank_delta: delta,
});

const POWER = {
  season_id: 3,
  season_year: 2017,
  through_week: 2,
  regular_season_weeks: 2,
  weights: { points_for_per_game: 0.4, all_play_win_pct: 0.25, win_pct: 0.2, recent_points_for_per_game: 0.15 },
  explainer: "Power score blends four within-season z-scores per the documented weights.",
  // Iceman is rated one spot above his record (a riser); Goose one below (a faller).
  rows: [row(1, "Iceman", 1.54, 1, 2), row(2, "Goose", -0.32, -1, 1)],
} as unknown as PowerRanking;

describe("PowerTable", () => {
  it("renders the ranking with power scores", () => {
    render(<PowerTable data={POWER} />);
    expect(screen.getByText("Iceman")).toBeInTheDocument();
    expect(screen.getByText("Goose")).toBeInTheDocument();
    expect(screen.getByText("1.54")).toBeInTheDocument();
    expect(screen.getByText("-0.32")).toBeInTheDocument();
  });

  it("shows the model-vs-standings movement (riser ▲ / faller ▼)", () => {
    render(<PowerTable data={POWER} />);
    expect(screen.getByText(/▲ 1/)).toBeInTheDocument();
    expect(screen.getByText(/▼ 1/)).toBeInTheDocument();
  });

  it("carries the 'how this is computed' explainer", () => {
    render(<PowerTable data={POWER} />);
    expect(screen.getByText(/How this is computed/i)).toBeInTheDocument();
    expect(screen.getByText(/within-season z-scores/i)).toBeInTheDocument();
  });
});
