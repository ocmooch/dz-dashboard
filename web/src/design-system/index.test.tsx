import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  Badge,
  Button,
  Card,
  CardHeader,
  Chip,
  DataGap,
  EmptyState,
  ErrorState,
  Pill,
  RecordLine,
  Skeleton,
  Sparkline,
  Stat,
  Tabs,
  Trophy,
  WeekStepper,
} from "./index";

describe("Card", () => {
  it("renders children inside a section with the base class", () => {
    const { container } = render(<Card>contents</Card>);
    const section = container.querySelector("section");
    expect(section).toBeInTheDocument();
    expect(section).toHaveClass("dz-card");
    expect(section).toHaveTextContent("contents");
  });

  it("adds the hover modifier only when hover is set", () => {
    const { container, rerender } = render(<Card>x</Card>);
    expect(container.querySelector("section")).not.toHaveClass("dz-card--hover");
    rerender(<Card hover>x</Card>);
    expect(container.querySelector("section")).toHaveClass("dz-card--hover");
  });

  it("passes through an extra className", () => {
    const { container } = render(<Card className="mt-4">x</Card>);
    expect(container.querySelector("section")).toHaveClass("mt-4");
  });
});

describe("CardHeader", () => {
  it("renders the title as a level-2 heading", () => {
    render(<CardHeader title="Standings" />);
    expect(screen.getByRole("heading", { level: 2, name: "Standings" })).toBeInTheDocument();
  });

  it("renders the eyebrow when provided and omits it otherwise", () => {
    const { rerender } = render(<CardHeader title="T" eyebrow="2024 season" />);
    expect(screen.getByText("2024 season")).toBeInTheDocument();
    rerender(<CardHeader title="T" />);
    expect(screen.queryByText("2024 season")).not.toBeInTheDocument();
  });

  it("renders an action node", () => {
    render(<CardHeader title="T" action={<button type="button">Edit</button>} />);
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });
});

describe("Stat", () => {
  it("renders its label, value and unit", () => {
    render(<Stat label="Points for" value="1,234.50" unit="pts" />);
    expect(screen.getByText("Points for")).toBeInTheDocument();
    expect(screen.getByText("1,234.50")).toBeInTheDocument();
    expect(screen.getByText("pts")).toBeInTheDocument();
  });

  it("applies the tone color class", () => {
    const { rerender } = render(<Stat label="W" value="10" tone="win" />);
    expect(screen.getByText("10")).toHaveClass("text-win");
    rerender(<Stat label="L" value="3" tone="loss" />);
    expect(screen.getByText("3")).toHaveClass("text-loss");
    rerender(<Stat label="A" value="7" tone="accent" />);
    expect(screen.getByText("7")).toHaveClass("text-accent");
  });

  it("defaults to the neutral text tone", () => {
    render(<Stat label="N" value="5" />);
    expect(screen.getByText("5")).toHaveClass("text-text");
  });
});

describe("Badge", () => {
  it("uses the base class by default", () => {
    render(<Badge>New</Badge>);
    const badge = screen.getByText("New");
    expect(badge).toHaveClass("dz-badge");
    expect(badge).not.toHaveClass("dz-badge--accent");
  });

  it("applies the accent and gap variant classes", () => {
    const { rerender } = render(<Badge variant="accent">A</Badge>);
    expect(screen.getByText("A")).toHaveClass("dz-badge--accent");
    rerender(<Badge variant="gap">G</Badge>);
    expect(screen.getByText("G")).toHaveClass("dz-badge--gap");
  });
});

describe("RecordLine", () => {
  it("shows wins and losses", () => {
    const { container } = render(<RecordLine wins={9} losses={4} ties={0} />);
    expect(container).toHaveTextContent("9");
    expect(container).toHaveTextContent("4");
    expect(screen.getByText("9")).toHaveClass("text-win");
    expect(screen.getByText("4")).toHaveClass("text-loss");
  });

  it("omits ties when there are none and shows them when present", () => {
    const { container, rerender } = render(<RecordLine wins={9} losses={4} ties={0} />);
    expect(container).not.toHaveTextContent("9-4-");
    rerender(<RecordLine wins={9} losses={4} ties={1} />);
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});

describe("Chip", () => {
  it("renders the name, an initials avatar, and an optional sub-label", () => {
    render(<Chip name="Joe Cool" sub="since 2010" />);
    expect(screen.getByText("Joe Cool")).toBeInTheDocument();
    expect(screen.getByText("JC")).toBeInTheDocument();
    expect(screen.getByText("since 2010")).toBeInTheDocument();
  });

  it("falls back to a dash and placeholder initials when the name is absent", () => {
    render(<Chip name={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("··")).toBeInTheDocument();
  });
});

describe("DataGap (the honesty component)", () => {
  it("exposes a note role with the dashed/hatched affordance class", () => {
    render(<DataGap />);
    const note = screen.getByRole("note");
    expect(note).toBeInTheDocument();
    expect(note).toHaveClass("dz-datagap");
  });

  it("applies the small-size modifier when requested", () => {
    render(<DataGap reason="no_meetings" size="sm" />);
    expect(screen.getByRole("note")).toHaveClass("dz-datagap--sm");
  });

  it("maps a known reason code to a human label", () => {
    render(<DataGap reason="season_unscored" />);
    expect(screen.getByRole("note")).toHaveTextContent("Per-player scoring not available for this season");
  });

  it("passes an unknown reason through verbatim", () => {
    render(<DataGap reason="some custom reason" />);
    expect(screen.getByRole("note")).toHaveTextContent("some custom reason");
  });

  it("falls back to a generic message with no reason", () => {
    render(<DataGap />);
    expect(screen.getByRole("note")).toHaveTextContent("Data not available");
  });

  // The N2.2 UI-side guarantee: a gap NEVER renders as a fake zero.
  it.each([
    "season_unscored",
    "no_scored_data",
    "availability_history_not_reconstructable",
    "no_availability_rows",
    "no_meetings",
    "team_defense_not_scored",
    undefined,
  ])("never renders a 0 for reason=%s", (reason) => {
    render(<DataGap reason={reason} />);
    expect(screen.getByRole("note").textContent).not.toMatch(/\b0\b/);
  });
});

describe("Skeleton", () => {
  it("renders a pulsing placeholder and forwards a className", () => {
    const { container } = render(<Skeleton className="h-6 w-20" />);
    const el = container.firstChild as HTMLElement;
    expect(el).toHaveClass("animate-pulse");
    expect(el).toHaveClass("h-6", "w-20");
  });
});

describe("EmptyState", () => {
  it("renders a title and an optional hint", () => {
    const { rerender } = render(<EmptyState title="Nothing here" hint="Try a different season" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Try a different season")).toBeInTheDocument();
    rerender(<EmptyState title="Nothing here" />);
    expect(screen.queryByText("Try a different season")).not.toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("renders the message and the 'Signal lost' eyebrow", () => {
    render(<ErrorState message="Could not load standings" />);
    expect(screen.getByText("Signal lost")).toBeInTheDocument();
    expect(screen.getByText("Could not load standings")).toBeInTheDocument();
  });

  it("shows a retry button only when onRetry is provided", () => {
    const { rerender } = render(<ErrorState message="x" />);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    const onRetry = vi.fn();
    rerender(<ErrorState message="x" onRetry={onRetry} />);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("invokes onRetry when the retry button is activated", async () => {
    const onRetry = vi.fn();
    render(<ErrorState message="x" onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("Button", () => {
  it("renders a secondary button by default", () => {
    render(<Button>Go</Button>);
    const btn = screen.getByRole("button", { name: "Go" });
    expect(btn).toHaveClass("dz-btn");
    expect(btn).not.toHaveClass("dz-btn--primary");
  });

  it("applies the primary and ghost variant classes", () => {
    const { rerender } = render(<Button variant="primary">P</Button>);
    expect(screen.getByRole("button", { name: "P" })).toHaveClass("dz-btn--primary");
    rerender(<Button variant="ghost">G</Button>);
    expect(screen.getByRole("button", { name: "G" })).toHaveClass("dz-btn--ghost");
  });

  it("is disabled and busy while loading, and does not fire onClick", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
    await userEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("Pill", () => {
  it("uses the base class by default and applies tones", () => {
    const { rerender } = render(<Pill>n</Pill>);
    expect(screen.getByText("n")).toHaveClass("dz-pill");
    expect(screen.getByText("n")).not.toHaveClass("dz-pill--accent");
    rerender(<Pill tone="win">w</Pill>);
    expect(screen.getByText("w")).toHaveClass("dz-pill--win");
    rerender(<Pill tone="loss">l</Pill>);
    expect(screen.getByText("l")).toHaveClass("dz-pill--loss");
  });
});

describe("Trophy", () => {
  it("renders the star marker with an optional count and label", () => {
    render(<Trophy label="titles" count={3} />);
    expect(screen.getByText("★")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("titles")).toBeInTheDocument();
  });
});

describe("WeekStepper", () => {
  it("disables prev at the floor and next at the ceiling", () => {
    const onChange = vi.fn();
    const { rerender } = render(<WeekStepper week={1} max={14} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Previous week" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next week" })).toBeEnabled();
    rerender(<WeekStepper week={14} max={14} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Next week" })).toBeDisabled();
  });

  it("steps the week on prev/next", async () => {
    const onChange = vi.fn();
    render(<WeekStepper week={5} max={14} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Next week" }));
    expect(onChange).toHaveBeenCalledWith(6);
    await userEvent.click(screen.getByRole("button", { name: "Previous week" }));
    expect(onChange).toHaveBeenCalledWith(4);
  });

  it("allows direct week selection", async () => {
    const onChange = vi.fn();
    render(<WeekStepper week={5} max={14} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText("Select week"), "12");
    expect(onChange).toHaveBeenCalledWith(12);
  });
});

describe("Tabs", () => {
  const tabs = [
    { id: "a", label: "Career" },
    { id: "b", label: "Seasons" },
  ] as const;

  it("marks the active tab selected and switches on click", async () => {
    const onChange = vi.fn();
    render(<Tabs tabs={[...tabs]} value="a" onChange={onChange} />);
    expect(screen.getByRole("tab", { name: "Career" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Seasons" })).toHaveAttribute("aria-selected", "false");
    await userEvent.click(screen.getByRole("tab", { name: "Seasons" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });
});

describe("Sparkline", () => {
  it("renders an accessible polyline for two or more points", () => {
    render(<Sparkline values={[1, 3, 2, 5]} />);
    const svg = screen.getByRole("img", { name: "trend sparkline" });
    expect(svg.querySelector("polyline")).toBeInTheDocument();
  });

  it("renders nothing for fewer than two points", () => {
    const { container } = render(<Sparkline values={[1]} />);
    expect(container.querySelector("svg")).toBeNull();
  });
});
