import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DraftPage } from "./DraftPage";

// The SPA reaches data only through the generated client; mocking it keeps these
// as pure presentation tests — no network, no business logic under test.
const get = vi.fn();
vi.mock("@/lib/api/client", () => ({ api: { GET: (...args: unknown[]) => get(...args) } }));

vi.mock("@/app/shell/SeasonContext", () => ({
  useSeasons: () => ({
    current: { season_id: 2, season_year: 2016, is_scored: true },
    seasons: [{ season_id: 2, season_year: 2016, is_scored: true }],
    setSeasonId: vi.fn(),
    isLoading: false,
  }),
}));

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const pick = (
  over: number,
  name: string,
  owner: string,
  pts: number,
  value: number,
  round = 1,
  pickInRound = over,
) => ({
  overall: over,
  round,
  pick_in_round: pickInRound,
  team_id: over,
  team_name: `${owner} 2016`,
  owner_id: over,
  owner_name: owner,
  player_id: over * 10,
  player_name: name,
  position: "RB",
  nfl_team: "DAL",
  season_year: 2016,
  season_points: pts,
  value,
  available: true,
  reason: null,
  adp: null,
  adp_sources: [],
  adp_source_spread: null,
  adp_format: null,
  adp_format_fallback: false,
  adp_delta: null,
  market_label: null,
  adp_available: false,
  adp_reason: "no_market_data",
});

const KELCE = {
  ...pick(1, "Travis Kelce", "Iceman", 22, -13.67),
  impact: -13.67,
  adp: 8.4,
  adp_sources: ["ffc", "mfl"],
  adp_source_spread: 1.0,
  adp_format: "full_ppr",
  adp_delta: -7.4,
  market_label: "reach",
  adp_available: true,
  adp_reason: null,
};
const CMC = {
  ...pick(4, "Christian McCaffrey", "Maverick", 55, 8.33),
  impact: 8.33,
  adp: 1.0,
  adp_sources: ["ffc"],
  adp_source_spread: 0.0,
  adp_format: "full_ppr",
  adp_delta: 3.0,
  market_label: "value",
  adp_available: true,
  adp_reason: null,
};
const ROUND_TWO = [
  pick(5, "Saquon Barkley", "Maverick", 50, 6.5, 2, 1),
  pick(6, "Ja'Marr Chase", "Slider", 44, 4.5, 2, 2),
  pick(7, "Josh Allen", "Goose", 47, 3.5, 2, 3),
  pick(8, "Amon-Ra St. Brown", "Iceman", 42, 1.5, 2, 4),
];

const BOARD = {
  season_id: 2,
  season_year: 2016,
  available: true,
  reason: null,
  num_teams: 12,
  rounds: [
    {
      round: 1,
      picks: [KELCE, pick(2, "Lamar Jackson", "Goose", 48, 7.5), pick(3, "Justin Jefferson", "Slider", 37, -3.5), CMC],
    },
    {
      round: 2,
      picks: ROUND_TWO,
    },
  ],
};

const VALUE = {
  season_id: 2,
  season_year: 2016,
  available: true,
  reason: null,
  definition: "Pick value = a player's regular-season fantasy points minus the slot average.",
  slot_window: 2,
  picks: [CMC, pick(2, "Lamar Jackson", "Goose", 48, 7.5), pick(3, "Justin Jefferson", "Slider", 37, -3.5), KELCE],
  steals: [CMC],
  busts: [KELCE],
  points_steals: [CMC],
  points_busts: [KELCE],
  adp_definition: "ADP is the consensus average draft position blended across public sources.",
  adp_weights: { ffc: 0.5, mfl: 0.3, sleeper: 0.2 },
  reaches: [KELCE],
  values: [CMC],
  leaderboard_limit: 9,
};

const TENDENCIES = {
  available: true,
  reason: null,
  definition: "Draft tendencies aggregate the market axis across every captured draft.",
  min_picks: 8,
  weights: { ffc: 0.5, mfl: 0.3, sleeper: 0.2 },
  managers: [
    {
      owner_id: 1,
      owner_name: "Iceman",
      team_name: "Iceman 2016",
      qualified: true,
      n_picks_with_adp: 12,
      mean_delta: -3.2,
      reach_rate: 0.6,
      value_rate: 0.3,
      discipline: 5.1,
      by_position: [{ position: "RB", n: 5, mean_delta: -4.0 }],
      sufficient: true,
    },
  ],
};

function routeByPath(path: string) {
  if (path === "/v1/seasons/{season_id}/draft") return envelope(BOARD);
  if (path === "/v1/seasons/{season_id}/draft/value") return envelope(VALUE);
  if (path === "/v1/draft/tendencies") return envelope(TENDENCIES);
  throw new Error(`unexpected path ${path}`);
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/draft"]}>
        <DraftPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  get.mockReset();
  get.mockImplementation((path: string) => Promise.resolve(routeByPath(path)));
});

afterEach(() => vi.clearAllMocks());

describe("DraftPage", () => {
  it("renders the draft board with picks deep-linking to players", async () => {
    renderPage();
    await screen.findByText("Round 1");
    expect(screen.getAllByTitle("Christian McCaffrey").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle("Lamar Jackson").length).toBeGreaterThan(0);
    // Each pick card links to the drafted player.
    const links = screen.getAllByRole("link");
    expect(links.some((a) => a.getAttribute("href") === "/players/40")).toBe(true);
  });

  it("renders rounds as a 12-column snake board", async () => {
    renderPage();
    const roundOne = await screen.findByLabelText("Round 1 snake picks");
    expect(roundOne).toHaveStyle({ gridTemplateColumns: "repeat(12, minmax(0, 1fr))" });

    const roundTwo = screen.getByLabelText("Round 2 snake picks");
    const picks = within(roundTwo).getAllByRole("link");
    expect(picks[0]).toHaveAttribute("title", "Amon-Ra St. Brown");
    expect(picks[picks.length - 1]).toHaveAttribute("title", "Saquon Barkley");
  });

  it("identifies steals and busts with signed value", async () => {
    renderPage();
    await screen.findByText("Steals");
    expect(screen.getByText("Busts")).toBeInTheDocument();
    // The steal carries a positive value, the bust a negative one.
    expect(screen.getAllByText("+8.33").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-13.67").length).toBeGreaterThan(0);
  });

  it("ranks busts by composite impact and surfaces the weighting breakdown", async () => {
    const comp = (over: Partial<Record<string, number | boolean>> = {}) => ({
      base_value: -40,
      normalized_value: -2,
      position_mean: 0,
      position_stddev: 20,
      weighted_eligible: true,
      cost_weight: 1,
      opportunity_weight: 1,
      bench_weeks: 0,
      ir_weeks: 0,
      opportunity_available: true,
      ...over,
    });
    // Same value (-40) and slot, but the bench-carried bust has the more negative
    // impact and must rank ahead of the IR-carried one.
    const benchBust = {
      ...pick(2, "Bench Bust", "Iceman", 0, -40, 1, 2),
      impact: -71.6,
      impact_components: comp({ opportunity_weight: 1.79, bench_weeks: 11 }),
    };
    const irBust = {
      ...pick(3, "IR Bust", "Goose", 0, -40, 1, 3),
      impact: -50,
      impact_components: comp({ opportunity_weight: 1.25, ir_weeks: 14 }),
    };
    const steal = {
      ...CMC,
      impact: 8.33,
      impact_components: comp({ base_value: 8.33 }),
    };
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/draft")
        return Promise.resolve(
          envelope({ ...BOARD, rounds: [{ round: 1, picks: [steal, benchBust, irBust] }] }),
        );
      if (path === "/v1/seasons/{season_id}/draft/value")
        return Promise.resolve(
          envelope({
            ...VALUE,
            impact_definition: "Draft impact = pick value scaled by how the pick was spent and carried.",
            weights: { cost_floor: 0.3, cost_curve: 1, opp_bench_weight: 1, opp_ir_weight: 0.25 },
            picks: [steal, benchBust, irBust],
            steals: [steal],
            busts: [benchBust, irBust],
            points_steals: [steal],
            points_busts: [benchBust, irBust],
            leaderboard_limit: 9,
          }),
        );
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    await screen.findByText("Busts");
    // Headline ranking number is the composite impact, with the honest value alongside.
    expect(screen.getAllByText("-71.60").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/val -40/).length).toBeGreaterThan(0);
    // The bench bust lists before the IR bust (more negative impact).
    const bench = screen.getByText("Bench Bust");
    const ir = screen.getByText("IR Bust");
    expect(bench.compareDocumentPosition(ir) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The weighting is legible: the carry multiplier and weeks ride in a tooltip.
    expect(screen.getAllByTitle(/carry 1\.79 \(11 bench/).length).toBeGreaterThan(0);
    // And the composite definition is shown to the reader.
    expect(screen.getByText(/scaled by how the pick was spent and carried/)).toBeInTheDocument();
  });

  it("switches leaderboards and chart together between weighted and points lenses", async () => {
    const weightedThird = {
      ...pick(40, "Terry McLaurin", "Fie", 80, -73.56, 4, 4),
      impact: -2.1,
      impact_components: {
        base_value: -73.56,
        normalized_value: -1.5,
        position_mean: 0,
        position_stddev: 50,
        weighted_eligible: true,
        weighted_reason: null,
        cost_weight: 0.8,
        opportunity_weight: 1.75,
        bench_weeks: 10,
        ir_weeks: 0,
        opportunity_available: true,
      },
    };
    const pointsThird = { ...pick(43, "James Conner", "Brigands", 60, -119.8, 4, 7), impact: -1 };
    const bustOne = { ...KELCE, impact: -3 };
    const bustTwo = { ...pick(2, "Mike Evans", "Fie", 40, -122.34), impact: -2.5 };
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/draft") return Promise.resolve(envelope(BOARD));
      if (path === "/v1/seasons/{season_id}/draft/value")
        return Promise.resolve(
          envelope({
            ...VALUE,
            picks: [CMC, bustOne, bustTwo, weightedThird, pointsThird],
            steals: [CMC],
            busts: [bustOne, bustTwo, weightedThird],
            points_steals: [CMC],
            points_busts: [bustOne, bustTwo, pointsThird],
            impact_definition: "Draft impact = position-normalized value.",
          }),
        );
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    expect(await screen.findByText("Terry McLaurin")).toBeInTheDocument();
    expect(screen.queryByText("James Conner")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Points" }));
    expect(await screen.findByText("James Conner")).toBeInTheDocument();
    expect(screen.queryByText("Terry McLaurin")).not.toBeInTheDocument();
    expect(screen.getByText("Pick value")).toBeInTheDocument();
    expect(screen.getByLabelText("Filter by team")).toBeInTheDocument();
    expect(screen.getByLabelText("Sort chart")).toHaveValue("metric");
  });

  it("expands each leaderboard three entries at a time and preserves dotted initials", async () => {
    const steals = Array.from({ length: 9 }, (_, index) => ({
      ...pick(index + 1, index === 3 ? "A.J. Green" : `Steal Player ${index + 1}`, "A Very Long Historical Team Name", 100, 20 - index),
      impact: 3 - index / 10,
    }));
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/draft")
        return Promise.resolve(envelope({ ...BOARD, rounds: [{ round: 1, picks: steals }] }));
      if (path === "/v1/seasons/{season_id}/draft/value")
        return Promise.resolve(
          envelope({
            ...VALUE,
            picks: steals,
            steals,
            busts: [],
            points_steals: steals,
            points_busts: [],
          }),
        );
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    await screen.findByText("Steal Player 3");
    const stealsCard = screen.getByText("Steals").closest("section");
    expect(stealsCard).not.toBeNull();
    expect(within(stealsCard as HTMLElement).queryByText("A.J. Green")).not.toBeInTheDocument();

    await userEvent.click(within(stealsCard as HTMLElement).getByRole("button", { name: "Show 3 more" }));
    expect(within(stealsCard as HTMLElement).getByText("A.J. Green")).toBeInTheDocument();
    expect(within(stealsCard as HTMLElement).getByRole("button", { name: "Collapse" })).toBeInTheDocument();
  });

  it("keeps the chart filters mounted when an ineligible position empties the chart", async () => {
    // A kicker has a points value but no weighted impact. Selecting K under the
    // weighted lens used to unmount the whole chart card (filters included),
    // stranding the user until a refresh. The controls must survive so the
    // selection stays recoverable.
    const wr = { ...CMC, impact: 8.33 };
    const kicker = { ...pick(2, "Justin Tucker", "Goose", 130, 30, 1, 2), position: "K", impact: null };
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/draft")
        return Promise.resolve(envelope({ ...BOARD, rounds: [{ round: 1, picks: [wr, kicker] }] }));
      if (path === "/v1/seasons/{season_id}/draft/value")
        return Promise.resolve(
          envelope({
            ...VALUE,
            picks: [wr, kicker],
            steals: [wr],
            busts: [],
            points_steals: [kicker],
            points_busts: [],
          }),
        );
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    const positionFilter = await screen.findByLabelText("Filter by position");

    await userEvent.selectOptions(positionFilter, "K");
    // The card and its controls remain; an honest empty state replaces the bars.
    expect(screen.getByLabelText("Filter by position")).toHaveValue("K");
    expect(screen.getByText(/aren’t part of the position-normalized impact model/i)).toBeInTheDocument();

    // Switching to the Points lens recovers a chart for the same selection.
    await userEvent.click(screen.getByRole("tab", { name: "Points" }));
    expect(screen.getByLabelText("Filter by position")).toHaveValue("K");
    expect(
      screen.queryByText(/aren’t part of the position-normalized impact model/i),
    ).not.toBeInTheDocument();
  });

  it("annotates a genuine season-long zero as DNP, not a missing-data gap", async () => {
    const cruz = {
      ...pick(3, "Victor Cruz", "Slider", 0, -50, 1, 3),
      zero_reason: "did_not_play_season",
      zero_detail:
        "Drafted but recorded no game stats all season — a season-long injury or " +
        "ineligibility, not missing data. Carried on the active bench.",
    };
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/draft")
        return Promise.resolve(envelope({ ...BOARD, rounds: [{ round: 1, picks: [cruz] }] }));
      if (path === "/v1/seasons/{season_id}/draft/value")
        return Promise.resolve(envelope({ ...VALUE, picks: [cruz], steals: [], busts: [cruz] }));
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    await screen.findByText("Round 1");
    // The 0 reads as a real total with a DNP marker explaining it — not a DataGap.
    expect(screen.getAllByText("DNP").length).toBeGreaterThan(0);
    expect(screen.getAllByTitle(/season-long injury or ineligibility/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/0 pts/)).toBeInTheDocument();
    expect(screen.queryByText(/value unavailable/i)).not.toBeInTheDocument();
  });

  it("labels a season whose draft was never captured, never inventing picks", async () => {
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/draft")
        return Promise.resolve(
          envelope({
            season_id: 2,
            season_year: 2016,
            available: false,
            reason: "draft_not_captured",
            num_teams: null,
            rounds: [],
          }),
        );
      return Promise.resolve(routeByPath(path));
    });
    renderPage();
    expect(await screen.findByText(/Draft not captured for this season/i)).toBeInTheDocument();
    expect(screen.queryByText("Round 1")).not.toBeInTheDocument();
  });

  it("shows the market (reach/value) axis on the board and a reach/value lens", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Round 1");
    // Market-only work stays off the initial weighted load.
    expect(screen.queryByText("ADP 8.40")).not.toBeInTheDocument();
    expect(screen.queryByText(/Reach by/)).not.toBeInTheDocument();
    expect(screen.queryByText("Reach / value vs outcome")).not.toBeInTheDocument();
    expect(screen.queryByText("Manager market tendencies")).not.toBeInTheDocument();
    expect(get.mock.calls.some(([path]) => path === "/v1/draft/tendencies")).toBe(false);

    // The Reach / value lens swaps Steals/Busts for Reaches/Values and reveals
    // the market-only exploratory pieces (quadrant + tendencies).
    await user.click(screen.getByRole("tab", { name: "Reach / value" }));
    expect(await screen.findByText("Reaches")).toBeInTheDocument();
    expect(screen.getByText("Values")).toBeInTheDocument();
    expect(screen.getAllByText(/Reach by/).length).toBeGreaterThan(0);
    expect(screen.getByText("Reach / value vs outcome")).toBeInTheDocument();
    expect(screen.getByText("Manager market tendencies")).toBeInTheDocument();

    // The board carries its own view control; switching it to Market reveals the
    // per-cell ADP read + reach amount (independent of the leaderboard lens above).
    const boardCard = screen.getByText("Draft board").closest("section") as HTMLElement;
    await user.click(within(boardCard).getByRole("tab", { name: "Market" }));
    expect(within(boardCard).getAllByText("ADP 8.40").length).toBeGreaterThan(0);
    expect(within(boardCard).getAllByText("7.40").length).toBeGreaterThan(0);
  });

  it("toggles the board between basic, performance, and market views", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Round 1");
    const boardCard = screen.getByText("Draft board").closest("section") as HTMLElement;

    // Basic default: the persistent identity carries position · NFL team, and the
    // board does not crowd in the steal/bust impact badge.
    expect(within(boardCard).getAllByText(/RB · DAL/).length).toBeGreaterThan(0);

    // Performance view surfaces the steal/bust callouts on the leaders.
    await user.click(within(boardCard).getByRole("tab", { name: "Performance" }));
    expect(within(boardCard).getByText("Top steal")).toBeInTheDocument();
    expect(within(boardCard).getByText("Top bust")).toBeInTheDocument();

    // Market view swaps in the per-cell ADP read.
    await user.click(within(boardCard).getByRole("tab", { name: "Market" }));
    expect(within(boardCard).getAllByText("ADP 8.40").length).toBeGreaterThan(0);
  });

  it("names all four reach/value outcome quadrants", async () => {
    const user = userEvent.setup();
    const reachHit = {
      ...pick(5, "Davante Adams", "Slider", 70, 14, 2, 1),
      impact: 5.2,
      adp: 11,
      adp_delta: -6,
      market_label: "reach",
      adp_available: true,
      adp_reason: null,
    };
    const valueMiss = {
      ...pick(6, "Todd Gurley", "Goose", 20, -18, 2, 2),
      impact: -4.4,
      adp: 3,
      adp_delta: 3,
      market_label: "value",
      adp_available: true,
      adp_reason: null,
    };
    get.mockImplementation((path: string) => {
      if (path === "/v1/seasons/{season_id}/draft")
        return Promise.resolve(envelope({ ...BOARD, rounds: [{ round: 1, picks: [KELCE, CMC, reachHit, valueMiss] }] }));
      if (path === "/v1/seasons/{season_id}/draft/value")
        return Promise.resolve(
          envelope({
            ...VALUE,
            picks: [KELCE, CMC, reachHit, valueMiss],
            reaches: [KELCE, reachHit],
            values: [CMC, valueMiss],
          }),
        );
      return Promise.resolve(routeByPath(path));
    });

    renderPage();
    await screen.findByText("Round 1");
    await user.click(screen.getByRole("tab", { name: "Reach / value" }));

    expect(await screen.findByText(/reach that hit or value that missed/i)).toBeInTheDocument();
    const quadrant = screen.getByLabelText("Reach/value vs outcome by pick");
    await user.click(within(quadrant).getByText("Data table"));
    expect(within(quadrant).getByText("Value that hit")).toBeInTheDocument();
    expect(within(quadrant).getByText("Reach that busted")).toBeInTheDocument();
    expect(within(quadrant).getByText("Reach that hit")).toBeInTheDocument();
    expect(within(quadrant).getByText("Value that missed")).toBeInTheDocument();
  });

  it("renders the manager market-tendencies table as an experimental market insight", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Round 1");
    await user.click(screen.getByRole("tab", { name: "Reach / value" }));
    expect(await screen.findByText("Manager market tendencies")).toBeInTheDocument();
    expect(screen.getByText("work in progress")).toBeInTheDocument();
    expect(screen.getAllByText("Reach rate").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Typical lean").length).toBeGreaterThan(0);
    expect(screen.getByText(/directional read on draft style/i)).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("reaches")).toBeInTheDocument();
  });
});
