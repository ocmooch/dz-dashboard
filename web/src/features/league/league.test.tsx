import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { LeagueHistoryPage } from "./LeagueHistoryPage";
import { RulesErasPage } from "./RulesErasPage";
import { StoriesPage } from "./StoriesPage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const TIMELINE = {
  league: {
    league_id: "DZTEST",
    name: "Danger Zone Test League",
    platform: "nfl_com",
    start_year: 2015,
    current_year: 2017,
    season_count: 3,
  },
  seasons: [
    {
      season_id: 1,
      season_year: 2015,
      status: "completed",
      league_size: 4,
      regular_season_weeks: 2,
      playoff_weeks: 1,
      championship_week: 3,
      champion: { team_id: 1, team_name: "Dynasty Crew", owner_id: 4, owner_name: "Slider" },
      runner_up: null,
      last_place: null,
      is_scored: false,
      schedule_source: "scraped",
      scoring_provenance: "nfl_com_authoritative_total",
      verification_status: "known_source_gap",
      source: "team_totals_without_player_reconstruction",
      changes: {
        league_size_changed: false,
        schedule_changed: false,
        scoring_availability_changed: false,
        details: [],
      },
    },
    {
      season_id: 2,
      season_year: 2016,
      status: "completed",
      league_size: 4,
      regular_season_weeks: 2,
      playoff_weeks: 1,
      championship_week: 3,
      champion: { team_id: 2, team_name: "Maverick 2016", owner_id: 1, owner_name: "Maverick" },
      runner_up: null,
      last_place: null,
      is_scored: true,
      schedule_source: "scraped",
      scoring_provenance: "nflverse_reconstructed",
      verification_status: "verification_pending",
      source: "computed_from_scored_player_rows",
      changes: {
        league_size_changed: false,
        schedule_changed: false,
        scoring_availability_changed: true,
        details: [
          {
            category: "scoring_rules",
            title: "Scoring rule changed",
            summary: "Receptions: 1 point",
            before: "Receptions: 1 point per 2 receptions",
            after: "Receptions: 1 point",
            source: "derived_from_db",
            certainty: "verified",
          },
        ],
      },
    },
  ],
};

const ERAS = {
  league: TIMELINE.league,
  eras: [
    {
      era_id: "era-1",
      label: "4-team league / 2-week regular season / team-total-only era",
      start_year: 2015,
      end_year: 2015,
      season_years: [2015],
      league_size: 4,
      regular_season_weeks: 2,
      playoff_weeks: 1,
      scoring_provenance: "nfl_com_authoritative_total",
      verification_status: "known_source_gap",
      certainty: "scraped",
    },
    {
      era_id: "era-2",
      label: "4-team league / 2-week regular season / reconstructed player-scoring era",
      start_year: 2016,
      end_year: 2017,
      season_years: [2016, 2017],
      league_size: 4,
      regular_season_weeks: 2,
      playoff_weeks: 1,
      scoring_provenance: "nflverse_reconstructed",
      verification_status: "verification_pending",
      certainty: "scraped",
    },
  ],
  changes: [
    {
      season_year: 2016,
      league_size_changed: false,
      schedule_changed: false,
      scoring_availability_changed: true,
      details: [
        {
          category: "scoring_rules",
          title: "Scoring rule changed",
          summary: "Receptions: 1 point",
          before: "Receptions: 1 point per 2 receptions",
          after: "Receptions: 1 point",
          source: "derived_from_db",
          certainty: "verified",
        },
      ],
    },
  ],
};

const STORIES = {
  stories: [
    {
      story_id: "biggest-blowout",
      title: "Biggest blowout",
      available: true,
      season_year: 2016,
      week: 1,
      matchup_id: 99,
      metric_label: "Margin",
      metric_value: 70,
      primary_team: { team_id: 1, team_name: "Maverick 2016", owner_id: 1, owner_name: "Maverick" },
      secondary_team: { team_id: 2, team_name: "Iceman 2016", owner_id: 2, owner_name: "Iceman" },
      caveat: null,
    },
    {
      story_id: "team-name-hall",
      title: "Team-name hall of fame",
      available: true,
      metric_label: "Repeated names",
      metric_value: 1,
      items: [{ team_name: "Dynasty Crew", seasons: 2 }],
      caveat: "Counts season-scoped team names, not durable manager identity.",
    },
  ],
};

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockImplementation((path: string) => {
    if (path === "/v1/league/timeline") return Promise.resolve(envelope(TIMELINE));
    if (path === "/v1/league/eras") return Promise.resolve(envelope(ERAS));
    if (path === "/v1/league/stories") return Promise.resolve(envelope(STORIES));
    return Promise.resolve(envelope({}));
  });
});

describe("LeagueHistoryPage", () => {
  it("renders seasons with champion and provenance labels", async () => {
    renderWithProviders(<LeagueHistoryPage />, ["/seasons"]);
    expect(await screen.findByText("League History")).toBeInTheDocument();
    expect(await screen.findByText("team totals")).toBeInTheDocument();
    expect(screen.getByText("Scoring rule changed")).toBeInTheDocument();
    expect(screen.getByText("Receptions: 1 point per 2 receptions")).toBeInTheDocument();
    expect(screen.getByText("Dynasty Crew")).toBeInTheDocument();
    expect(screen.getByText("Champion · Slider")).toBeInTheDocument();
  });
});

describe("RulesErasPage", () => {
  it("renders derived eras and material changes", async () => {
    renderWithProviders(<RulesErasPage />, ["/rules"]);
    expect(await screen.findByText("Rules & Eras")).toBeInTheDocument();
    expect(await screen.findByText(/team-total-only era/i)).toBeInTheDocument();
    expect(screen.getByText("Before: Receptions: 1 point per 2 receptions")).toBeInTheDocument();
  });
});

describe("StoriesPage", () => {
  it("renders story cards without frontend metric computation", async () => {
    renderWithProviders(<StoriesPage />, ["/stories"]);
    expect(await screen.findByText("Biggest blowout")).toBeInTheDocument();
    expect(screen.getByText("70.00")).toBeInTheDocument();
    expect(screen.getByText("Dynasty Crew")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Box score" })).toHaveAttribute("href", "/matchups/99");
  });
});
