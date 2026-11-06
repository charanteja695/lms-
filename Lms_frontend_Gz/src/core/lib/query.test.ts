import { describe, expect, it } from "vitest";

import { buildQueryString, compact, diffForUpdate } from "@/core/lib/query";

describe("buildQueryString", () => {
  it("skips empty values so the API never receives blank filters", () => {
    expect(buildQueryString({ role: "student", status: "", page: 2, search_text: undefined, email_verified: false })).toBe(
      "role=student&page=2&email_verified=false",
    );
  });

  it("repeats a list as one key per value, the way the API reads lists", () => {
    expect(buildQueryString({ status: ["applied", "ai_screened"], q: "asha" })).toBe("status=applied&status=ai_screened&q=asha");
  });
});

describe("compact", () => {
  it("removes empty strings, undefined and empty objects recursively", () => {
    expect(compact({ a: "", b: "x", c: { d: "", e: undefined }, f: [{ g: "" , h: 1 }] })).toEqual({ b: "x", f: [{ h: 1 }] });
  });
});

describe("diffForUpdate", () => {
  it("returns only changed fields and turns cleared values into null", () => {
    const before = { personal_info: { first_name: "Priya", phone: "+919812345678", middle_name: "" }, account: { email: "a@x.com" } };
    const after = { personal_info: { first_name: "Priya", phone: "", middle_name: "Devi" }, account: { email: "a@x.com" } };
    expect(diffForUpdate(before, after)).toEqual({ personal_info: { phone: null, middle_name: "Devi" } });
  });

  it("returns undefined when nothing changed", () => {
    expect(diffForUpdate({ a: { b: "1" } }, { a: { b: "1" } })).toBeUndefined();
  });

  it("sends arrays whole when they change", () => {
    expect(diffForUpdate({ list: [{ name: "A" }] }, { list: [{ name: "A" }, { name: "B" }] })).toEqual({ list: [{ name: "A" }, { name: "B" }] });
  });
});
