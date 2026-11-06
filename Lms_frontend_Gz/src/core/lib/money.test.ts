import { describe, expect, it } from "vitest";

import { formatMinor } from "@/core/lib/money";

describe("formatMinor", () => {
  it("divides the minor unit by 100", () => {
    expect(formatMinor(1234567, "INR")).toContain("12,345.67");
    expect(formatMinor(250, "USD")).toContain("2.50");
  });
  it("shows a dash for a missing amount", () => {
    expect(formatMinor(null, "INR")).toBe("—");
  });
});
