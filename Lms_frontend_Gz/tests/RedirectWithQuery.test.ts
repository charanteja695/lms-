import { describe, expect, it } from "vitest";

import { computeRedirectUrl } from "./RedirectWithQuery";

describe("RedirectWithQuery - Query Parameter Preservation & Default Injection", () => {
  it("redirects cleanly when no query params and no default params are provided", () => {
    const result = computeRedirectUrl("", "/user-management/hierarchy");
    expect(result).toBe("/user-management/hierarchy");
  });

  it("appends default parameters when original search query is empty", () => {
    const result = computeRedirectUrl("", "/user-management/users", { category: "admins" });
    expect(result).toBe("/user-management/users?category=admins");
  });

  it("preserves single existing query parameter while applying default parameters", () => {
    const result = computeRedirectUrl("?page=2", "/user-management/users", { category: "students" });
    expect(result).toBe("/user-management/users?page=2&category=students");
  });

  it("preserves multiple search, pagination, and filter parameters", () => {
    const originalSearch = "?search=Alex&status=active&page=3&per_page=50";
    const result = computeRedirectUrl(originalSearch, "/user-management/users", { category: "staff" });
    
    const url = new URL(result, "http://localhost");
    expect(url.pathname).toBe("/user-management/users");
    expect(url.searchParams.get("category")).toBe("staff");
    expect(url.searchParams.get("search")).toBe("Alex");
    expect(url.searchParams.get("status")).toBe("active");
    expect(url.searchParams.get("page")).toBe("3");
    expect(url.searchParams.get("per_page")).toBe("50");
  });

  it("does NOT overwrite existing parameter if key is already present in search", () => {
    const originalSearch = "?category=staff";
    const result = computeRedirectUrl(originalSearch, "/user-management/users", { category: "students" });
    expect(result).toBe("/user-management/users?category=staff");
  });

  it("redirects legacy /institutions to /user-management/hierarchy?view=table preserving institution search", () => {
    const originalSearch = "?search=Institute&page=2";
    const result = computeRedirectUrl(originalSearch, "/user-management/hierarchy", { view: "table" });
    
    const url = new URL(result, "http://localhost");
    expect(url.pathname).toBe("/user-management/hierarchy");
    expect(url.searchParams.get("view")).toBe("table");
    expect(url.searchParams.get("search")).toBe("Institute");
    expect(url.searchParams.get("page")).toBe("2");
  });

  it("redirects legacy /organisation to /user-management/hierarchy without adding default params", () => {
    const result = computeRedirectUrl("", "/user-management/hierarchy");
    expect(result).toBe("/user-management/hierarchy");
  });

  it("handles complex encoded query parameters like institution names and spaces", () => {
    const originalSearch = "?organization_label=GenZ%20Test%20College&search=John%20Doe";
    const result = computeRedirectUrl(originalSearch, "/user-management/users", { category: "students" });
    
    const url = new URL(result, "http://localhost");
    expect(url.searchParams.get("organization_label")).toBe("GenZ Test College");
    expect(url.searchParams.get("search")).toBe("John Doe");
    expect(url.searchParams.get("category")).toBe("students");
  });
});
