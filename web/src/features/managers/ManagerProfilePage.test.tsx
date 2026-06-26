import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { ManagerProfilePage } from "./ManagerProfilePage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const CAREER = {
  owner_id: 1,
  display_name: "Alpha",
  seasons_played: 3,
  total_wins: 30,
  total_losses: 12,
  total_ties: 0,
  total_points_for: 4200,
  championships: 1,
  sackos: 1,
  best_finish: 1,
  avg_finish: 2.5,
  consistency: {
    available: true,
    reason: null,
    weekly_points_stdev: 18.2,
    rank_among_owners: 2,
    best_season_year: 2020,
    best_season_points_for: 1800.5,
    signature: "ceiling scorer",
    weeks_sampled: 42,
    top_week_rate: 0.31,
    floor_week_rate: 0.12,
    above_median_rate: 0.64,
    average_weekly_rank: 4.25,
    weekly_volatility: 0.82,
  },
  trophy_case: [
    { season_year: 2020, team_name: "Alpha FC", finish: 1, is_champion: true, is_sacko: false },
    { season_year: 2018, team_name: "Alpha FC", finish: 12, is_champion: false, is_sacko: true },
  ],
};

const SEASONS = [
  // record-only season: 0 PF -> must render an honest gap, not "0".
  { season_id: 10, season_year: 2014, team_id: 100, team_name: "Old Alpha", wins: 8, losses: 6, ties: 0, points_for: 0, final_rank: 5, made_playoffs: false, is_champion: false, is_sacko: false },
  // scored, championship season.
  { season_id: 11, season_year: 2020, team_id: 101, team_name: "Alpha FC", wins: 12, losses: 2, ties: 0, points_for: 1800.5, final_rank: 1, made_playoffs: true, is_champion: true, is_sacko: false },
  // a Sacko (toilet-bowl) season — the result cell must show the 💩 anti-trophy.
  { season_id: 12, season_year: 2018, team_id: 102, team_name: "Alpha FC", wins: 3, losses: 11, ties: 0, points_for: 1200.0, final_rank: 12, made_playoffs: false, is_champion: false, is_sacko: true },
];

const TRAJ = [
  { season_year: 2014, final_rank: 5, points_for: 0 },
  { season_year: 2020, final_rank: 1, points_for: 1800.5 },
];

const MATRIX = {
  owners: [
    { owner_id: 1, display_name: "Alpha" },
    { owner_id: 2, display_name: "Bravo" },
  ],
  cells: [
    { a: 1, b: 2, games: 4, a_win_pct: 0.75 },
    { a: 2, b: 1, games: 4, a_win_pct: 0.25 },
  ],
};

// A story with a signature win + a favourite victim present, but the nemesis and
// luck lines gated out (null) — the band must render the present lines and omit
// the absent ones entirely, never a forced 0.
const STORY = {
  owner: { owner_id: 1, display_name: "Alpha" },
  available: true,
  signature_win: {
    opponent: { owner_id: 2, display_name: "Bravo" },
    owner_score: 150,
    opponent_score: 80,
    margin: 70,
    season_year: 2020,
    week: 4,
    matchup_id: 555,
    is_playoff: false,
  },
  heartbreak: null,
  high_water_mark: null,
  nemesis: null,
  favorite_victim: {
    opponent: { owner_id: 2, display_name: "Bravo" },
    games: 4,
    wins: 3,
    losses: 1,
    ties: 0,
    win_pct: 0.75,
  },
  luckiest_season: null,
  unluckiest_season: null,
};

function mockEndpoints() {
  mockGet.mockImplementation((path: string) => {
    if (path === "/v1/owners/{owner_id}") return Promise.resolve({ data: { data: CAREER, meta: {} } });
    if (path === "/v1/owners/{owner_id}/seasons")
      return Promise.resolve({ data: { data: { owner_id: 1, display_name: "Alpha", seasons: SEASONS }, meta: {} } });
    if (path === "/v1/owners/{owner_id}/trajectory")
      return Promise.resolve({ data: { data: { owner_id: 1, display_name: "Alpha", points: TRAJ }, meta: {} } });
    if (path === "/v1/owners/{owner_id}/story") return Promise.resolve({ data: { data: STORY, meta: {} } });
    if (path === "/v1/owners/rivalry-matrix") return Promise.resolve({ data: { data: MATRIX, meta: {} } });
    return Promise.resolve({ error: { detail: "unexpected" } });
  });
}

function renderProfile(id = "1") {
  return renderWithProviders(
    <Routes>
      <Route path="/managers/:ownerId" element={<ManagerProfilePage />} />
    </Routes>,
    [`/managers/${id}`],
  );
}

beforeEach(() => mockGet.mockReset());

describe("ManagerProfilePage", () => {
  it("renders the career header, trophy case, and season table", async () => {
    mockEndpoints();
    renderProfile();

    expect(await screen.findByRole("heading", { name: "Alpha" })).toBeInTheDocument();
    // Trophy case section.
    expect(screen.getByText("Hardware")).toBeInTheDocument();
    // Season table has both seasons, scored PF rendered as a number.
    expect(screen.getByText("1,800.50")).toBeInTheDocument();
  });

  it("brands a Sacko season with the 💩 anti-trophy in the season table", async () => {
    mockEndpoints();
    renderProfile();

    // The 2018 Sacko season (PF 1,200.00) — its result cell carries the 💩.
    const sackoRow = (await screen.findByText("1,200.00")).closest("tr")!;
    expect(within(sackoRow).getByText(/💩/)).toBeInTheDocument();
  });

  it("shows an honest gap for a record-only (unscored) season instead of a 0", async () => {
    mockEndpoints();
    renderProfile();

    const oldRow = (await screen.findByText("Old Alpha")).closest("tr")!;
    expect(within(oldRow).getByText(/scoring not available for this season/i)).toBeInTheDocument();
    expect(within(oldRow).queryByText("0")).not.toBeInTheDocument();
  });

  it("links rivalry snapshot rows to the pairwise page", async () => {
    mockEndpoints();
    renderProfile();

    // Scope to the rivalry snapshot via its unique "GP" line (the story band also
    // links to Bravo as the favourite victim).
    const rival = (await screen.findByText(/4 GP/)).closest("a")!;
    expect(rival).toHaveAttribute("href", "/rivalries/1/vs/2");
    expect(rival).toHaveTextContent("4 GP");
  });

  it("links to the latest roster through the latest team season", async () => {
    mockEndpoints();
    renderProfile();

    const latest = await screen.findByRole("link", { name: /Latest roster \(2020\)/i });
    expect(latest).toHaveAttribute("href", "/teams/101");
  });

  it("renders a week-relative scoring tendency instead of a raw boom-bust split", async () => {
    mockEndpoints();
    renderProfile();

    expect(await screen.findByText("Scoring Tendency")).toBeInTheDocument();
    expect(screen.getByText("ceiling scorer")).toBeInTheDocument();
    expect(screen.getByText("31%")).toBeInTheDocument();
    expect(screen.getByText("12%")).toBeInTheDocument();
    expect(screen.getByText("64%")).toBeInTheDocument();
    expect(screen.getByText("42 weeks")).toBeInTheDocument();
    expect(screen.getByText("vol 0.82")).toBeInTheDocument();
    expect(screen.queryByText("Weekly stdev")).not.toBeInTheDocument();
  });

  it("leads with the Your Story band, links to receipts, and omits gated-out lines", async () => {
    mockEndpoints();
    renderProfile();

    // The lead band renders with its present superlatives.
    expect(await screen.findByText("Your Story")).toBeInTheDocument();
    expect(screen.getByText("Signature win")).toBeInTheDocument();
    expect(screen.getByText("Favorite victim")).toBeInTheDocument();

    // Signature win deep-links to the box score; favourite victim to the pairwise page.
    const sig = screen.getByText("Signature win").closest("a")!;
    expect(sig).toHaveAttribute("href", "/matchups/555");
    const vic = screen.getByText("Favorite victim").closest("a")!;
    expect(vic).toHaveAttribute("href", "/rivalries/1/vs/2");

    // Gated-out (null) superlatives are simply absent — never a forced 0 / empty row.
    expect(screen.queryByText("Kryptonite")).not.toBeInTheDocument();
    expect(screen.queryByText("Heartbreak")).not.toBeInTheDocument();
    expect(screen.queryByText("Luckiest season")).not.toBeInTheDocument();
    expect(screen.queryByText("Robbed")).not.toBeInTheDocument();
  });

  it("renders a not-found state when the owner does not exist", async () => {
    mockGet.mockResolvedValue({ error: { detail: "No owner with id 999" } });
    renderProfile("999");
    expect(await screen.findByText("Manager not found")).toBeInTheDocument();
  });
});
