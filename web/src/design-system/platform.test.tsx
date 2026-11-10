import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { capabilityGapText, capabilityStateLabel, isRendered, provenanceText } from "@/lib/platform";

import { CapabilityGate, EraMarker, ProvenanceNote } from "./index";

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
