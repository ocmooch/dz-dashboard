import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ThisWeek } from "./ThisWeek";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const team = (team_id: number, name: string, score: number | null, is_winner = false) => ({
  team_id,
  team_name: name,
  owner_name: `Owner ${team_id}`,
  score,
  is_winner,
  is_sacko: false,
  entering_record: { wins: 4, losses: 4, ties: 0 },
});

const CURRENT = {
  available: true,
  reason: null,
  season_id: 5,
  season_year: 2026,
  platform: "sleeper",
  platform_label: "Sleeper",
  regular_season_weeks: 14,
  last_finalized_week: 8,
  pending_week: 9,
  latest_results: [
    {
      matchup_id: 113,
      is_playoff: false,
      pending: false,
      team_a: team(1, "Alpha", 140.5, true),
      team_b: team(2, "Bravo", 120.25),
      margin: 20.25,
      winner_team_id: 1,
      flags: [],
    },
  ],
  pending_pairings: [
    {
      matchup_id: 125,
      is_playoff: false,
      pending: true,
      team_a: team(3, "Charlie", null),
      team_b: team(4, "Delta", null),
      margin: null,
      winner_team_id: null,
      flags: [],
    },
  ],
  standings_top: [
    {
      rank: 1,
      team_id: 1,
      team_name: "Alpha",
      owner_id: 1,
      owner_name: "Owner 1",
      wins: 7,
      losses: 1,
      ties: 0,
      points_for: 1082.34,
      points_against: 989.2,
      win_pct: 0.875,
      streak: { result: "W", length: 6 },
    },
  ],
};

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.clearAllMocks());

describe("ThisWeek", () => {
  it("shows the last final week's results, the pending pairings unscored, and standings", async () => {
    get.mockResolvedValue(envelope(CURRENT));
    wrap(<ThisWeek />);
    expect(await screen.findByText("This week")).toBeInTheDocument();
    expect(screen.getByText(/through week 8 · week 9 awaiting final/)).toBeInTheDocument();
    expect(screen.getByText("Week 8 results")).toBeInTheDocument();
    expect(screen.getByText("140.50")).toBeInTheDocument();
    // Pending pairings: names shown, no score and no zero.
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    expect(screen.getAllByText("Awaiting final").length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText("No score yet")).toHaveLength(2);
    expect(screen.queryByText("0.00")).not.toBeInTheDocument();
    // Cards deep-link to the box score.
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/matchups/113");
    expect(hrefs).toContain("/matchups/125");
  });

  it("renders nothing off-season", async () => {
    get.mockResolvedValue(envelope({ available: false, reason: "no_current_season" }));
    const { container } = wrap(<ThisWeek />);
    await waitFor(() => expect(get).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
