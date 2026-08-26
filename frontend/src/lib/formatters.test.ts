import { describe, expect, it } from "vitest";
import {
  budgetUsagePct,
  decimalToNumber,
  formatCompactCurrency,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatNumber,
  resolveFormatterLocale,
} from "./formatters";

describe("decimalToNumber", () => {
  it("returns the number when value is a number", () => {
    expect(decimalToNumber(42)).toBe(42);
    expect(decimalToNumber(0)).toBe(0);
    expect(decimalToNumber(-3.14)).toBe(-3.14);
  });

  it("parses numeric strings into numbers", () => {
    expect(decimalToNumber("123")).toBe(123);
    expect(decimalToNumber("0.5")).toBe(0.5);
    expect(decimalToNumber("-7")).toBe(-7);
  });

  it("returns 0 for null and undefined", () => {
    expect(decimalToNumber(null)).toBe(0);
    expect(decimalToNumber(undefined)).toBe(0);
  });

  it("returns 0 for non-finite values (NaN/Infinity)", () => {
    expect(decimalToNumber("not a number")).toBe(0);
    expect(decimalToNumber(Number.NaN)).toBe(0);
    expect(decimalToNumber(Infinity)).toBe(0);
    expect(decimalToNumber("Infinity")).toBe(0);
  });
});

describe("formatCurrency", () => {
  it("formats USD with 2 decimal places and thousands separator", () => {
    expect(formatCurrency(1234.5, "USD", "en-US")).toBe("$1,234.50");
    expect(formatCurrency("1000000", "USD", "en-US")).toBe("$1,000,000.00");
  });

  it("formats CNY currency", () => {
    const result = formatCurrency(1234.5, "CNY", "en-US");
    // Modern Node Intl disambiguates CNY from JPY using the "CN¥" prefix
    expect(result).toContain("¥");
    expect(result).toContain("1,234.50");
  });

  it("defaults to USD when no currency is provided", () => {
    expect(formatCurrency(99.999, "USD", "en-US")).toBe("$100.00");
  });

  it("returns $0.00 for null and undefined inputs", () => {
    expect(formatCurrency(null, "USD", "en-US")).toBe("$0.00");
    expect(formatCurrency(undefined, "USD", "en-US")).toBe("$0.00");
  });

  it("formats negative values with a leading minus sign", () => {
    expect(formatCurrency(-12.5, "USD", "en-US")).toBe("-$12.50");
  });

  it("coerces non-finite inputs to $0.00", () => {
    expect(formatCurrency("not-a-number", "USD", "en-US")).toBe("$0.00");
  });

  it("uses Chinese number conventions when the UI locale is zh-CN", () => {
    expect(formatCurrency(1234.5, "USD", "zh-CN")).toContain("US$");
    expect(formatCurrency(1234.5, "USD", "zh-CN")).toContain("1,234.50");
  });
});

describe("formatCompactCurrency", () => {
  it("formats large numbers in compact notation", () => {
    expect(formatCompactCurrency(1_500_000, "USD", "en-US")).toBe("$1.5M");
    expect(formatCompactCurrency(2_000_000_000, "USD", "en-US")).toBe("$2.0B");
  });

  it("respects the currency parameter", () => {
    const result = formatCompactCurrency(1_500_000, "CNY", "en-US");
    expect(result).toContain("1.5M");
    expect(result).toContain("¥");
  });

  it("returns a compact $0 value for null/undefined", () => {
    const result = formatCompactCurrency(null, "USD", "en-US");
    expect(result).toMatch(/\$/);
    expect(result).toMatch(/0/);
  });

  it("keeps at most 1 fractional digit", () => {
    const result = formatCompactCurrency(1_550_000, "USD", "en-US");
    expect(result).toBe("$1.6M");
  });
});

describe("locale-aware formatters", () => {
  it("defaults to the product locale and accepts English explicitly", () => {
    document.documentElement.lang = "zh-CN";
    expect(resolveFormatterLocale()).toBe("zh-CN");
    expect(resolveFormatterLocale("en-GB")).toBe("en-US");
  });

  it("formats localized numbers and dates", () => {
    expect(formatNumber(1_234_567, {}, "en-US")).toBe("1,234,567");
    expect(formatDate("2026-08-13T04:05:06Z", "zh-CN")).toContain("2026年8月13日");
    expect(formatDateTime("2026-08-13T04:05:06Z", "en-US")).toMatch(/Aug 13, 2026/);
  });
});

describe("budgetUsagePct", () => {
  it("returns 0 when limit is 0", () => {
    expect(budgetUsagePct(100, 0)).toBe(0);
  });

  it("returns 0 when limit is negative", () => {
    expect(budgetUsagePct(100, -50)).toBe(0);
  });

  it("calculates percentage and rounds to the nearest integer", () => {
    expect(budgetUsagePct(50, 100)).toBe(50);
    expect(budgetUsagePct(33, 99)).toBe(33); // 33.33... → 33
    expect(budgetUsagePct(66, 99)).toBe(67); // 66.66... → 67
  });

  it("accepts string inputs", () => {
    expect(budgetUsagePct("50", "100")).toBe(50);
    expect(budgetUsagePct("25", "100")).toBe(25);
  });

  it("caps the percentage at 100", () => {
    expect(budgetUsagePct(150, 100)).toBe(100);
    expect(budgetUsagePct(200, 50)).toBe(100);
  });

  it("returns 0 when spent is 0", () => {
    expect(budgetUsagePct(0, 100)).toBe(0);
  });
});
