import { date, eur, eurM, int, multiple, pct, quarter, shortKey } from "../src/shared/lib/format";

describe("formatting", () => {
  it("writes money, shares and multiples the same way everywhere", () => {
    expect(eur("1234567.891")).toBe("1,234,568 EUR");
    expect(eur("-2362.5", 2)).toBe("-2,362.50 EUR");
    expect(eurM("61700000")).toBe("61.7 m EUR");
    expect(eurM("950000")).toBe("950,000 EUR");
    expect(pct("-0.061")).toBe("-6.1 %");
    expect(multiple("1.0335")).toBe("1.03x");
    expect(int(1200)).toBe("1,200");
  });

  it("says n/a instead of NaN for missing figures", () => {
    for (const f of [eur, eurM, pct, multiple, int]) {
      expect(f(null)).toBe("n/a");
      expect(f("")).toBe("n/a");
    }
  });

  it("names quarters and dates without a time zone shift", () => {
    expect(quarter("2026-09-30")).toBe("Q3 2026");
    expect(quarter("2025-12-31")).toBe("Q4 2025");
    expect(date("2026-09-30")).toBe("30 Sept 2026");
    expect(date(null)).toBe("not yet");
  });

  it("shortens client keys but keeps both ends", () => {
    expect(shortKey("ck_bd6109e2ef2b6c4b")).toBe("ck_bd61…2b6c4b");
    expect(shortKey(null)).toBe("");
  });
});
