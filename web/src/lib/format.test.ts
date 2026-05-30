import { describe, expect, it } from "vitest";

import { initials, num, ordinal, pct, record } from "./format";

describe("record", () => {
  it("renders W-L when there are no ties", () => {
    expect(record(10, 3, 0)).toBe("10-3");
  });

  it("renders W-L-T when ties are present", () => {
    expect(record(8, 4, 1)).toBe("8-4-1");
  });

  it("treats a negative tie count as no ties", () => {
    // ties only show when strictly positive
    expect(record(5, 5, 0)).toBe("5-5");
  });
});

describe("num", () => {
  it("renders two decimals by default", () => {
    expect(num(12.5)).toBe("12.50");
    expect(num(0)).toBe("0.00");
  });

  it("groups thousands", () => {
    expect(num(1500.25)).toBe("1,500.25");
  });

  it("honors a custom decimal-place count", () => {
    expect(num(12.5, 1)).toBe("12.5");
  });

  it("renders an em dash for null/undefined — never a fake 0", () => {
    expect(num(null)).toBe("—");
    expect(num(undefined)).toBe("—");
  });
});

describe("pct", () => {
  it("renders a whole-number percentage", () => {
    expect(pct(0.5)).toBe("50%");
    expect(pct(0.333)).toBe("33%");
  });

  it("renders an em dash for absent values", () => {
    expect(pct(null)).toBe("—");
    expect(pct(undefined)).toBe("—");
  });
});

describe("ordinal", () => {
  it("uses the right suffix for the common cases", () => {
    expect(ordinal(1)).toBe("1st");
    expect(ordinal(2)).toBe("2nd");
    expect(ordinal(3)).toBe("3rd");
    expect(ordinal(4)).toBe("4th");
    expect(ordinal(21)).toBe("21st");
  });

  it("uses 'th' for the teens", () => {
    expect(ordinal(11)).toBe("11th");
    expect(ordinal(12)).toBe("12th");
    expect(ordinal(13)).toBe("13th");
    expect(ordinal(111)).toBe("111th");
  });

  it("renders an em dash for absent values", () => {
    expect(ordinal(null)).toBe("—");
    expect(ordinal(undefined)).toBe("—");
  });
});

describe("initials", () => {
  it("uses the first letter of the first two name parts", () => {
    expect(initials("Joe Cool")).toBe("JC");
  });

  it("falls back to the first two letters of a single name", () => {
    expect(initials("Madonna")).toBe("Ma");
  });

  it("collapses extra whitespace", () => {
    expect(initials("  spaced   name ")).toBe("sn");
  });

  it("returns a placeholder for an empty or absent name", () => {
    expect(initials("")).toBe("··");
    expect(initials(null)).toBe("··");
    expect(initials(undefined)).toBe("··");
  });
});
