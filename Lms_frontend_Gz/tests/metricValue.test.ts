import { describe, expect, it } from "vitest";

import { metricValue } from "@/modules/analytics/dashboards/components/metricValue";

describe("metricValue", () => {
  it("shows rates (fractions) as percentages", () => expect(metricValue(0.725, "percent")).toBe("72.5%"));
  it("treats billing amounts as paise and CTC as whole rupees", () => {
    expect(metricValue(150000, "inr")).toContain("1,500");
    expect(metricValue(1500, "rupees")).toContain("1,500");
  });
  it("shows a dash for a missing value", () => expect(metricValue(null, "score")).toBe("—"));
  it("rounds counts", () => expect(metricValue(1234.4)).toBe((1234).toLocaleString()));
});
