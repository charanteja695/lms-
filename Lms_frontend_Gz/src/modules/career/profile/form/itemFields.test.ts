import { describe, expect, it } from "vitest";

import { toFormValues, toItemData } from "./itemFields";

describe("career item form mapping", () => {
  it("drops empty fields and splits lines and lists", () => {
    const data = toItemData("project", { name: " Chess engine ", url: "", technologies: "Python, numpy , ", description: "", start_date: "2025-01", end_date: "", bullets: "Wrote a search\n\n Added tests " });
    expect(data).toEqual({ name: "Chess engine", technologies: ["Python", "numpy"], start_date: "2025-01", bullets: ["Wrote a search", "Added tests"] });
  });

  it("round-trips an item's data through the form", () => {
    const data = { company: "Acme", title: "Intern", current: true, bullets: ["Built X", "Shipped Y"] };
    expect(toItemData("experience", toFormValues("experience", data))).toEqual(data);
  });

  it("handles skill data with name only and drops category", () => {
    const data = { name: " TypeScript " };
    expect(toItemData("skill", data as any)).toEqual({ name: "TypeScript" });
  });
});
