import { describe, expect, it } from "vitest";

import { ctcRange, experienceLabel, formatCtc, stipendLabel } from "./format";

describe("job-portal formatting", () => {
  it("reads INR in lakhs and other currencies in thousands", () => {
    expect(formatCtc(600_000)).toBe("₹6 L");
    expect(formatCtc(1_250_000)).toBe("₹12.5 L");
    expect(formatCtc(85_000, "USD")).toBe("USD 85k");
    expect(ctcRange({ ctc_min: 600_000, ctc_max: 1_200_000, currency: "INR" })).toBe("₹6 L – ₹12 L");
    expect(ctcRange({ ctc_min: null, ctc_max: null, currency: "INR" })).toBeNull();
  });

  it("describes the experience window", () => {
    expect(experienceLabel(0, null)).toBe("Freshers");
    expect(experienceLabel(12, 36)).toBe("1–3 yrs");
    expect(experienceLabel(18, null)).toBe("1.5+ yrs");
  });
});

describe("stipendLabel", () => {
  it("reads an internship's pay and length", () => {
    expect(stipendLabel({ stipend_per_month: 25_000, duration_months: 6, currency: "INR" })).toBe("₹25,000/month · 6 months");
    expect(stipendLabel({ stipend_per_month: null, duration_months: 1, currency: "INR" })).toBe("1 month");
    expect(stipendLabel({ stipend_per_month: null, duration_months: null, currency: "INR" })).toBeNull();
  });
});
