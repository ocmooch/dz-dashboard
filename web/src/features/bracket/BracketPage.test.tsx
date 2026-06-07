import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BracketPage } from "./BracketPage";

const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({
    current: { season_id: 1, season_year: 2015, is_scored: false },
    seasons: [{ season_id: 1, season_year: 2015, is_scored: false }],
    setSeasonId: vi.fn(),
    isLoading: false,
  }),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const BRACKET = {
  season_id: 1,
  season_year: 2015,
  regular_season_weeks: 2,
  available: true,
  reason: null,
  caveat:
    "Post-regular-season matchups from the source data. Championship versus consolation structure is shown only when source flags distinguish it.",
  weeks: [
    {
      week: 3,
      games: [
        {
          matchup_id: 10,
          is_playoff: true,
          is_consolation: false,
          winner_team_id: 1,
          team_a: {
            team_id: 1,
            team_name: "Slider 2015",
            owner_id: 1,
            owner_name: "Slider",
            score: 120,
            is_winner: true,
          },
          team_b: {
            team_id: 2,
            team_name: "Maverick 2015",
            owner_id: 2,
            owner_name: "Maverick",
            score: 110,
            is_winner: false,
          },
        },
        {
          matchup_id: 12,
          is_playoff: true,
          is_consolation: true,
          winner_team_id: 3,
          team_a: {
            team_id: 3,
            team_name: "Goose 2015",
            owner_id: 3,
            owner_name: "Goose",
            score: 90,
            is_winner: true,
          },
          team_b: {
            team_id: 4,
            team_name: "Iceman 2015",
            owner_id: 4,
            owner_name: "Iceman",
            score: 50,
            is_winner: false,
          },
        },
      ],
    },
  ],
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/bracket"]}>
        <BracketPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  get.mockResolvedValue(envelope(BRACKET));
});

afterEach(() => vi.clearAllMocks());

describe("BracketPage", () => {
  it("renders caveated post-regular-season matchup cards", async () => {
    renderPage();
    expect(await screen.findByText("Bracket")).toBeInTheDocument();
    expect(await screen.findByText(/Post-regular-season matchups/i)).toBeInTheDocument();
    expect(screen.getByText("Week 3")).toBeInTheDocument();
    expect(screen.getByText("Slider")).toBeInTheDocument();
    expect(screen.getByText("Maverick")).toBeInTheDocument();
    expect(screen.getByText("playoff")).toBeInTheDocument();
    expect(screen.getByText("consolation")).toBeInTheDocument();
    expect(screen.getAllByRole("link").some((a) => a.getAttribute("href") === "/matchups/10")).toBe(true);
  });

  it("renders a DataGap when no bracket rows are available", async () => {
    get.mockResolvedValueOnce(
      envelope({
        ...BRACKET,
        available: false,
        reason: "bracket_unavailable",
        weeks: [],
      }),
    );

    renderPage();
    expect(await screen.findByText(/Bracket data isn't available/i)).toBeInTheDocument();
    expect(screen.queryByText("Week 3")).not.toBeInTheDocument();
  });
});
