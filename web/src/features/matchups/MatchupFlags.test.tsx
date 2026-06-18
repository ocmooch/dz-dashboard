import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MatchupFlags } from "./MatchupFlags";

type Flag = Parameters<typeof MatchupFlags>[0]["flags"][number];

const flag = (over: Partial<Flag>): Flag => ({
  kind: "blowout",
  label: "Blowout",
  tone: "loss",
  team_id: null,
  detail: null,
  ...over,
});

describe("MatchupFlags", () => {
  it("renders nothing when there are no flags", () => {
    const { container } = render(<MatchupFlags flags={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("maps each tone to its CSS modifier and shows the label + tooltip", () => {
    render(
      <MatchupFlags
        flags={[
          flag({ kind: "season_high", label: "Season high", tone: "win", detail: "168.4 — season's highest team score" }),
          flag({ kind: "nailbiter", label: "Nailbiter", tone: "accent" }),
          flag({ kind: "dud", label: "Dud", tone: "muted" }),
          flag({ kind: "tough_luck", label: "Tough luck", tone: "warn" }),
        ]}
      />,
    );
    expect(screen.getByText("Season high").closest(".dz-flag")).toHaveClass("dz-flag--win");
    expect(screen.getByText("Nailbiter").closest(".dz-flag")).toHaveClass("dz-flag--accent");
    expect(screen.getByText("Dud").closest(".dz-flag")).toHaveClass("dz-flag--muted");
    expect(screen.getByText("Tough luck").closest(".dz-flag")).toHaveClass("dz-flag--warn");
    expect(screen.getByText("Season high").closest(".dz-flag")).toHaveAttribute(
      "title",
      "168.4 — season's highest team score",
    );
  });

  it("falls back to the muted modifier for an unknown tone", () => {
    render(<MatchupFlags flags={[flag({ tone: "brandnew", label: "Mystery" })]} />);
    expect(screen.getByText("Mystery").closest(".dz-flag")).toHaveClass("dz-flag--muted");
  });
});
