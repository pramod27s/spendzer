import { describe, expect, it } from "vitest";

import { distinctCategoryColors, MUTED_SERIES, SERIES_VARS } from "./colors";
import { formatCompactINR, formatINR, monthBounds, pctChange, toNumber } from "./format";

describe("formatINR", () => {
  it("uses Indian digit grouping", () => {
    expect(formatINR("123456")).toBe("₹1,23,456");
    expect(formatINR(10000000)).toBe("₹1,00,00,000");
  });
  it("shows paise when asked and signs negatives", () => {
    expect(formatINR("2450.5", { paise: true })).toBe("₹2,450.50");
    expect(formatINR(-640)).toBe("−₹640");
    expect(formatINR(25, { sign: true })).toBe("+₹25");
  });
  it("treats missing values as zero", () => {
    expect(formatINR(null)).toBe("₹0");
    expect(toNumber("not a number")).toBe(0);
  });
});

describe("formatCompactINR", () => {
  it("abbreviates thousands, lakhs and crores", () => {
    expect(formatCompactINR(950)).toBe("₹950");
    expect(formatCompactINR(12000)).toBe("₹12K");
    expect(formatCompactINR(1250)).toBe("₹1.3K");
    expect(formatCompactINR(120000)).toBe("₹1.2L");
    expect(formatCompactINR(34000000)).toBe("₹3.4Cr");
  });
});

describe("pctChange / monthBounds", () => {
  it("returns null without a base", () => {
    expect(pctChange(100, 0)).toBeNull();
    expect(pctChange(150, 100)).toBe(50);
  });
  it("gives the first and last day of a month", () => {
    expect(monthBounds(new Date(2026, 1, 14))).toEqual({ start: "2026-02-01", end: "2026-02-28" });
  });
});

describe("distinctCategoryColors", () => {
  it("keeps each category's own hue when they differ", () => {
    expect(distinctCategoryColors(["#2a78d6", "#eb6834"])).toEqual([SERIES_VARS[0], SERIES_VARS[1]]);
  });
  it("re-slots a later category that shares a hue with an earlier one", () => {
    const [a, b] = distinctCategoryColors(["#eb6834", "#eb6834"]);
    expect(a).toBe(SERIES_VARS[1]);
    expect(b).not.toBe(a);
  });
  it("keeps neutral grey for 'Other'", () => {
    expect(distinctCategoryColors(["#898781"])).toEqual([MUTED_SERIES]);
  });
});
