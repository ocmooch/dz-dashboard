import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BarCompare, Heatmap, LineTrend, RankFlow, StackedBreakdown } from "./index";

const data = [
  { wk: 1, a: 100, b: 90 },
  { wk: 2, a: 110, b: 95 },
];
const series = [
  { key: "a", label: "Alpha" },
  { key: "b", label: "Bravo" },
];

describe("cartesian chart wrappers", () => {
  it.each([
    ["LineTrend", LineTrend],
    ["BarCompare", BarCompare],
    ["StackedBreakdown", StackedBreakdown],
  ] as const)("%s renders an accessible figure with a data-table fallback", (title, Comp) => {
    render(<Comp data={data} series={series} xKey="wk" xLabel="Week" title={title} />);
    expect(screen.getByRole("figure", { name: title })).toBeInTheDocument();
    // data-table fallback carries the raw numbers for screen readers
    expect(screen.getByText("Data table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Week" })).toBeInTheDocument();
    expect(screen.getAllByText("110").length).toBeGreaterThan(0);
  });

  it("RankFlow renders with a reversed rank axis figure", () => {
    render(
      <RankFlow data={data} series={series} xKey="wk" xLabel="Week" title="Rank flow" teamCount={2} />,
    );
    expect(screen.getByRole("figure", { name: "Rank flow" })).toBeInTheDocument();
  });
});

describe("Heatmap", () => {
  const rows = ["AA", "BB"];
  const cols = ["AA", "BB"];
  // diagonal inert; AA-vs-BB = 60; BB-vs-AA = null (never met)
  const values = [
    [null, 60],
    [null, null],
  ];

  it("renders an honest DataGap for null cells, never a 0", () => {
    render(<Heatmap rows={rows} cols={cols} values={values} title="Matrix" />);
    const gapCells = screen.getAllByTitle("never met / not in coverage");
    expect(gapCells.length).toBeGreaterThan(0);
    gapCells.forEach((cell) => expect(cell.textContent).not.toMatch(/\b0\b/));
  });

  it("fires onSelect on click and Enter for live cells only", async () => {
    const onSelect = vi.fn();
    render(<Heatmap rows={rows} cols={cols} values={values} title="Matrix" onSelect={onSelect} />);
    const cell = screen.getByRole("gridcell", { name: "AA vs BB: 60%" });
    await userEvent.click(cell);
    expect(onSelect).toHaveBeenCalledWith(0, 1);
    cell.focus();
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledTimes(2);
  });
});
