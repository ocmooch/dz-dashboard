import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  aggregationNoteText,
  capabilityGapText,
  capabilityStateLabel,
  draftTypeLabel,
  isRendered,
  officialPointsNote,
  provenanceText,
  scoringEraText,
  slotNoteText,
  tradeAssetsText,
} from "@/lib/platform";

import { CapabilityGate, EraMarker, ProvenanceNote, throughWeekText } from "./index";

describe("EraMarker", () => {
  it("renders the platform label as a neutral uppercase mono marker", () => {
    const { container } = render(<EraMarker label="Sleeper" />);
    const el = container.querySelector(".dz-era-marker");
    expect(el).toHaveTextContent("Sleeper");
    expect(el).toHaveClass("uppercase", "font-mono", "text-muted");
  });

  it("renders nothing without a label", () => {
    const { container } = render(<EraMarker label={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("CapabilityGate", () => {
  const child = <span>the data</span>;

  it.each(["available", "partial", "derived"])("renders children when %s", (state) => {
    render(
      <CapabilityGate capKey="standings" cap={{ state }} platform="sleeper">
        {child}
      </CapabilityGate>,
    );
    expect(screen.getByText("the data")).toBeInTheDocument();
  });

  it("renders the standard DataGap with the capability copy when not on the platform", () => {
    render(
      <CapabilityGate capKey="lineup_change_log" cap={{ state: "not_on_platform" }} platform="sleeper">
        {child}
      </CapabilityGate>,
    );
    expect(screen.queryByText("the data")).not.toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Lineup-change history isn't available from Sleeper.");
  });

  it("renders the not-yet copy for an in-progress week", () => {
    render(
      <CapabilityGate capKey="potential_points" cap={{ state: "not_yet" }} platform="sleeper">
        {child}
      </CapabilityGate>,
    );
    expect(screen.getByRole("note")).toHaveTextContent("Not available until this week is final.");
  });

  it("renders nothing at all for not_used (no copy, no DataGap)", () => {
    const { container } = render(
      <CapabilityGate capKey="official_divisions" cap={{ state: "not_used" }} platform="sleeper">
        {child}
      </CapabilityGate>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ProvenanceNote", () => {
  it("renders a one-line footnote", () => {
    render(<ProvenanceNote>Bracket derived from NFL.com playoff results.</ProvenanceNote>);
    expect(screen.getByText("Bracket derived from NFL.com playoff results.")).toHaveClass("dz-provenance");
  });

  it("renders nothing when empty", () => {
    const { container } = render(<ProvenanceNote>{null}</ProvenanceNote>);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("lib/platform copy", () => {
  it("prefers the BFF note, then the 03 §3 copy, then a plain fallback", () => {
    expect(
      capabilityGapText("faab_failed_bids", { state: "not_on_platform", note: "From BFF" }, "nfl_com"),
    ).toBe("From BFF");
    expect(capabilityGapText("faab_failed_bids", { state: "not_on_platform" }, "nfl_com")).toBe(
      "NFL.com didn't record unsuccessful waiver bids.",
    );
    expect(capabilityGapText("co_owners", { state: "not_on_platform" }, "nfl_com")).toBe(
      "Co owners isn't available from NFL.com.",
    );
  });

  it("knows which states render and how to label them", () => {
    expect(isRendered({ state: "not_used" })).toBe(false);
    expect(isRendered({ state: "not_on_platform" })).toBe(true);
    expect(capabilityStateLabel("not_used")).toBe("");
    expect(provenanceText("official_brackets", "nfl_com")).toBe(
      "Bracket derived from NFL.com playoff results.",
    );
    expect(provenanceText("official_brackets", "sleeper")).toBeNull();
  });
});

describe("Sleeper D3 copy", () => {
  it("describes the pick/FAAB side of a trade", () => {
    expect(
      tradeAssetsText({ picks_in: [], picks_out: [{ season: 2027, round: 2 }], faab_in: 7, faab_out: 0 }),
    ).toBe("Draft pick / FAAB: sent 2027 round 2 pick, received $7 FAAB");
  });

  it("names the official points source and the in-progress weeks", () => {
    expect(officialPointsNote("sleeper")).toBe("Official player points from Sleeper.");
    expect(officialPointsNote(null)).toBeNull();
    expect(throughWeekText(8, 9)).toBe("through week 8 · week 9 awaiting final");
    expect(throughWeekText(8)).toBe("through week 8");
    expect(slotNoteText("bench_or_reserve")).toMatch(/Bench or reserve/);
    expect(slotNoteText(null)).toBeNull();
  });
});

describe("cross-era aggregation copy (D4)", () => {
  const partial = [{ season_year: 2026, through_week: 8 }];

  it("renders nothing for a null note", () => {
    expect(aggregationNoteText(null)).toBeNull();
    expect(aggregationNoteText(undefined)).toBeNull();
  });

  it("names the in-progress season and its last final week", () => {
    const note = {
      used_seasons: [2025, 2026],
      excluded_seasons: [],
      partial_seasons: partial,
      reason: "in_progress_partial",
    };
    expect(aggregationNoteText(note)).toBe("Includes 2026 through week 8 (in progress; subject to change).");
    expect(aggregationNoteText({ ...note, partial_seasons: [{ season_year: 2026, through_week: 0 }] })).toBe(
      "Includes 2026 (no week final yet) (in progress; subject to change).",
    );
  });

  it("splits single-game and season-total records", () => {
    const note = {
      used_seasons: [2025, 2026],
      excluded_seasons: [2026],
      partial_seasons: partial,
      reason: "season_totals_exclude_in_progress",
    };
    expect(aggregationNoteText(note)).toBe(
      "Single-game records include 2026 through week 8. Season totals leave out 2026 (in progress).",
    );
  });

  it("shows a scoring-era chip only when the league spans more than one era", () => {
    const era = { era_id: 2, label: "2011–2025", start: 2011, end: 2025 };
    expect(scoringEraText(era, 3)).toBe("2011–2025 scoring");
    expect(scoringEraText(era, 1)).toBeNull();
    expect(scoringEraText(null, 3)).toBeNull();
  });

  it("labels known draft types and hides unknown ones", () => {
    expect(draftTypeLabel("snake")).toBe("Snake draft");
    expect(draftTypeLabel(null)).toBeNull();
    expect(draftTypeLabel("mystery")).toBeNull();
  });
});
