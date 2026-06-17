import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";

import { LeagueHistoryPage } from "./LeagueHistoryPage";
import { StoriesPage } from "./StoriesPage";

vi.mock("@/lib/api/client", () => ({ api: { GET: vi.fn() } }));
import { api } from "@/lib/api/client";
const mockGet = api.GET as unknown as ReturnType<typeof vi.fn>;

const envelope = (data: unknown) => ({ data: { data, meta: {} }, error: undefined });

const CHANGE_DEFAULTS = {
  changed_at: null,
  participants_joined: null,
  participants_left: null,
  description_gap: false,
};

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
      era_id: "era-1",
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
      era_id: "era-2",
      changes: {
        league_size_changed: false,
        schedule_changed: false,
        scoring_availability_changed: true,
        details: [
          {
            ...CHANGE_DEFAULTS,
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
  it("renders seasons with champion, change detail, and the eras strip", async () => {
    renderWithProviders(<LeagueHistoryPage />, ["/timeline"]);
    expect(await screen.findByText("League Timeline")).toBeInTheDocument();
    // Structural shape lives in the eras strip, not repeated per season row.
    expect(await screen.findByText("Eras at a Glance")).toBeInTheDocument();
    expect(screen.getByText("NFL.com team totals")).toBeInTheDocument();
    expect(screen.getByText("Reconstructed player scoring")).toBeInTheDocument();
    // The rich timeline change detail is intact.
    expect(screen.getByText("Scoring rule changed")).toBeInTheDocument();
    expect(screen.getByText("Receptions: 1 point per 2 receptions")).toBeInTheDocument();
    expect(screen.getByText("Dynasty Crew")).toBeInTheDocument();
    expect(screen.getByText("Champion · Slider")).toBeInTheDocument();
  });

  it("renders tiers, the in-season marker, missing-context, and expandable members", async () => {
    const member = {
      ...CHANGE_DEFAULTS,
      category: "divisions",
      title: "Division assignment",
      human_label: "Division assignment",
      summary: "changed Alpha Squad's Division from '1' to '2'",
      before: "1",
      after: "2",
      source: "nfl_com_transaction_log",
      certainty: "source_limited",
      tier: "T3",
      phase: "off_season",
      missing_context: false,
      members: [],
      canonical_type: "division_assignment",
    };
    const tiered = {
      league: TIMELINE.league,
      seasons: [
        {
          ...TIMELINE.seasons[1],
          season_id: 9,
          season_year: 2018,
          changes: {
            league_size_changed: false,
            schedule_changed: false,
            scoring_availability_changed: false,
            details: [
              {
                ...CHANGE_DEFAULTS,
                category: "divisions",
                title: "Division realignment",
                human_label: "Division realignment",
                summary: "Division realignment — 1 team reassigned.",
                source: "nfl_com_transaction_log",
                certainty: "verified",
                tier: "T1",
                phase: "off_season",
                missing_context: false,
                members: [member],
                canonical_type: "division_assignment",
              },
              {
                ...CHANGE_DEFAULTS,
                category: "playoffs",
                title: "Playoff field",
                human_label: "Playoff field",
                summary: "scott finalized the playoff field on 2018-12-02.",
                source: "nfl_com_transaction_log",
                certainty: "source_limited",
                tier: "T2",
                phase: "in_season",
                missing_context: true,
                members: [],
                canonical_type: "playoff_teams",
              },
            ],
          },
        },
      ],
    };
    mockGet.mockImplementation((path: string) => {
      if (path === "/v1/league/timeline") return Promise.resolve(envelope(tiered));
      return Promise.resolve(envelope({}));
    });

    renderWithProviders(<LeagueHistoryPage />, ["/timeline"]);
    // Wait for the async timeline to render an event before asserting on it.
    expect(await screen.findByText("Division realignment")).toBeInTheDocument();
    // T1 "Major" badge (legend + the event) and in-season marker (legend + event).
    expect(screen.getAllByText("Major").length).toBeGreaterThan(0);
    expect(screen.getAllByText("in-season").length).toBeGreaterThan(0);
    // Missing-context affordance — never a fabricated value.
    expect(screen.getByText(/Context not recorded/)).toBeInTheDocument();
    // Members are collapsed until expanded.
    expect(screen.queryByText(/changed Alpha Squad/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Show 1/ }));
    expect(screen.getByText(/changed Alpha Squad/)).toBeInTheDocument();
  });
});

describe("eras strip (merged from the old Rules & Eras page)", () => {
  it("shows era spans and folds rule changes into the timeline, not a separate log", async () => {
    renderWithProviders(<LeagueHistoryPage />, ["/timeline"]);
    await screen.findByText("Eras at a Glance");
    // Multi-season era span is rendered from /v1/league/eras (unique to the strip).
    expect(screen.getByText("2016–2017")).toBeInTheDocument();
    // The known source gap surfaces as a labelled badge, never a fabricated value.
    expect(screen.getByText("source gap")).toBeInTheDocument();
    // The old degraded "Before: …" material-changes list is gone; the timeline's
    // before/after rendering owns this now.
    expect(screen.queryByText("Before: Receptions: 1 point per 2 receptions")).not.toBeInTheDocument();
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
