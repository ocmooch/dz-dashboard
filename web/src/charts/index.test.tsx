import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  BarCompare,
  Beeswarm,
  DivergingBars,
  Heatmap,
  LegacySpine,
  LineTrend,
  MarginLine,
  MetricScatter,
  RankFlow,
  StackedBreakdown,
  StreamArea,
} from "./index";

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
    expect(screen.getAllByText("Alpha").length).toBeGreaterThan(0);
  });

  it("RankFlow accepts champion/Sacko series markers without breaking the fallback", () => {
    const marked = [
      { key: "a", label: "Alpha", marker: "champion" as const },
      { key: "b", label: "Bravo", marker: "sacko" as const },
    ];
    render(
      <RankFlow data={data} series={marked} xKey="wk" xLabel="Week" title="Race" teamCount={2} animate={false} />,
    );
    expect(screen.getByRole("figure", { name: "Race" })).toBeInTheDocument();
  });

  it("StreamArea renders stacked areas with a data-table fallback", () => {
    render(<StreamArea data={data} series={series} xKey="wk" xLabel="Week" title="Stream" />);
    expect(screen.getByRole("figure", { name: "Stream" })).toBeInTheDocument();
    expect(screen.getByText("Data table")).toBeInTheDocument();
  });
});

describe("DivergingBars", () => {
  const luck = [
    { label: "Iceman", value: 2.4, note: "lucky" },
    { label: "Maverick", value: 0, note: "even" },
    { label: "Goose", value: -2.2, note: "robbed" },
  ];

  it("renders an accessible figure with a data-table fallback carrying signed values", () => {
    render(<DivergingBars data={luck} title="Luck" xLabel="Wins vs expected" />);
    expect(screen.getByRole("figure", { name: "Luck" })).toBeInTheDocument();
    expect(screen.getByText("Data table")).toBeInTheDocument();
    // both the lucky (+) and robbed (−) magnitudes survive in the fallback
    expect(screen.getByText("2.4")).toBeInTheDocument();
    expect(screen.getByText("-2.2")).toBeInTheDocument();
  });
});

describe("Beeswarm", () => {
  const groups = [
    { label: "Steady", values: [100, 102, 98, 101] },
    { label: "BoomBust", values: [60, 140, 70, 130] },
  ];

  it("renders a figure with a per-group summary fallback table", () => {
    render(<Beeswarm groups={groups} title="Spread" xLabel="Points" />);
    expect(screen.getByRole("figure", { name: "Spread" })).toBeInTheDocument();
    expect(screen.getByText("Data table")).toBeInTheDocument();
    // both group labels appear in the summary fallback
    expect(screen.getByText("Steady")).toBeInTheDocument();
    expect(screen.getByText("BoomBust")).toBeInTheDocument();
  });
});

describe("MarginLine", () => {
  const points = [
    { label: "2015 W1", margin: 10 },
    { label: "2016 W1", margin: 70, championship: true },
    { label: "2017 W2", margin: -5 },
  ];

  it("renders a figure with a signed-margin data-table fallback", () => {
    render(<MarginLine points={points} title="Rivalry" />);
    expect(screen.getByRole("figure", { name: "Rivalry" })).toBeInTheDocument();
    expect(screen.getByText("Data table")).toBeInTheDocument();
    expect(screen.getByText("-5")).toBeInTheDocument();
  });
});

describe("MetricScatter", () => {
  const points = [
    { x: 2.5, y: 30, label: "Sharp", note: "92% · 1400 PF" },
    { x: -3, y: -20, label: "Leaky", note: "84% · 1200 PF" },
  ];

  it("renders a figure with a two-axis fallback table", () => {
    render(<MetricScatter points={points} title="IQ" xLabel="Eff" yLabel="PF" />);
    expect(screen.getByRole("figure", { name: "IQ" })).toBeInTheDocument();
    expect(screen.getByText("Data table")).toBeInTheDocument();
    expect(screen.getByText("Sharp (92% · 1400 PF)")).toBeInTheDocument();
  });
});

describe("LegacySpine", () => {
  const seasons = [
    { season_year: 2018, final_rank: 12, is_champion: false, is_sacko: true },
    // a rank-less / in-progress season — must read as a gap, never a 0.
    { season_year: 2019, final_rank: null, is_champion: false, is_sacko: false },
    { season_year: 2020, final_rank: 1, is_champion: true, is_sacko: false },
  ];

  it("renders an accessible figure with a data-table fallback", () => {
    render(<LegacySpine seasons={seasons} title="Spine" />);
    expect(screen.getByRole("figure", { name: "Spine" })).toBeInTheDocument();
    expect(screen.getByText("Data table")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Season" })).toBeInTheDocument();
  });

  it("marks champion and Sacko seasons and never plots a gap as 0", () => {
    render(<LegacySpine seasons={seasons} title="Spine" />);
    // The champion/Sacko grammar survives in the data-table fallback.
    expect(screen.getByText("Champion")).toBeInTheDocument();
    expect(screen.getByText("Sacko")).toBeInTheDocument();
    // The rank-less 2019 season shows an em dash for finish — not a 0.
    const gapRow = screen.getByText("2019").closest("tr")!;
    expect(within(gapRow).getByText("—")).toBeInTheDocument();
    expect(within(gapRow).queryByText("0")).not.toBeInTheDocument();
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
