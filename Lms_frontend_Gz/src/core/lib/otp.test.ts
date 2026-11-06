import { describe, expect, it } from "vitest";

import { cleanOtp, isCompleteOtp } from "./otp";

describe("one-time codes", () => {
  it("keeps only the digits, so pasted or spaced codes work", () => {
    expect(cleanOtp(" 123 456 ")).toBe("123456");
    expect(cleanOtp("123-456")).toBe("123456");
    expect(cleanOtp("")).toBe("");
  });
  it("is complete only at six digits", () => {
    expect(isCompleteOtp("123456")).toBe(true);
    expect(isCompleteOtp("")).toBe(false);
    expect(isCompleteOtp("12345")).toBe(false);
  });
});
