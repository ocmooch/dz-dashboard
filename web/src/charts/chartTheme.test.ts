import { describe, expect, it } from "vitest";

import { chartTheme, heatColor, seriesColor } from "./chartTheme";

describe("chartTheme", () => {
  it("returns the six-color series ramp with token fallbacks", () => {
    const t = chartTheme();
    expect(t.series).toHaveLength(6);
    expect(t.series[0]).toBe("#ff6a1a");
  });

  it("wraps the series ramp by index", () => {
    expect(seriesColor(0)).toBe(seriesColor(6));
    expect(seriesColor(1)).toBe("#5aa9ff");
  });
});

describe("heatColor", () => {
  it("anchors loss-red, steel and win-green at 0 / 50 / 100", () => {
    expect(heatColor(0)).toBe("rgb(239, 71, 97)");
    expect(heatColor(50)).toBe("rgb(57, 65, 78)");
    expect(heatColor(100)).toBe("rgb(52, 211, 158)");
  });

  it("clamps out-of-range input", () => {
    expect(heatColor(-20)).toBe(heatColor(0));
    expect(heatColor(140)).toBe(heatColor(100));
  });
});
