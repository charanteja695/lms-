import { describe, it, expect } from "vitest";

describe("Student Type Categorization Business Logic", () => {
  it("categorizes independent student correctly when organization_id is missing or individual", () => {
    const userWithoutOrg: { role: string; institution: { organization_id?: string; code?: string } | null } = { role: "student", institution: null };
    const isIndep1 = userWithoutOrg.role === "student" && !userWithoutOrg.institution?.organization_id;
    expect(isIndep1).toBe(true);

    const userWithIndivOrg = { role: "student", institution: { organization_id: "123", code: "INDIVIDUAL" } };
    const hasValidOrgId = Boolean(
      userWithIndivOrg.institution?.organization_id &&
      userWithIndivOrg.institution.code !== "INDIVIDUAL"
    );
    const isIndep2 = userWithIndivOrg.role === "student" && !hasValidOrgId;
    expect(isIndep2).toBe(true);
  });

  it("categorizes institution student correctly when organization_id is valid and not individual", () => {
    const userWithInst = { role: "student", institution: { organization_id: "373316671525681166", code: "CHARANTEJA85" } };
    const hasValidOrgId = Boolean(
      userWithInst.institution?.organization_id &&
      userWithInst.institution.code !== "INDIVIDUAL"
    );
    const isInstStudent = userWithInst.role === "student" && hasValidOrgId;
    const isIndep = userWithInst.role === "student" && !hasValidOrgId;
    expect(isInstStudent).toBe(true);
    expect(isIndep).toBe(false);
  });

  it("identifies institution head role without confusing with student subscriptions", () => {
    const userHead = { role: "institution_head", institution: { organization_id: "373316671525681166", code: "CHARANTEJA85" } };
    const isHead = userHead.role === "institution_head";
    const isStudent = userHead.role === "student";
    expect(isHead).toBe(true);
    expect(isStudent).toBe(false);
  });

  it("filters out restricted menus for institution students", () => {
    const restricted = new Set(["my_subscription", "my_payment_requests", "payment_history"]);
    const isInstitutionStudent = true;

    const navItems = [
      { menu: "browse_courses", label: "Browse Courses" },
      { menu: "my_subscription", label: "My Subscription" },
      { menu: "my_payment_requests", label: "My Payment Requests" },
      { menu: "payment_history", label: "Payment History" },
      { menu: "my_learning", label: "My Learning" },
    ];

    const visibleItems = navItems.filter((i) => {
      if (isInstitutionStudent && restricted.has(i.menu)) {
        return false;
      }
      return true;
    });

    const visibleKeys = visibleItems.map((i) => i.menu);
    expect(visibleKeys).toEqual(["browse_courses", "my_learning"]);
    expect(visibleKeys).not.toContain("my_subscription");
    expect(visibleKeys).not.toContain("my_payment_requests");
    expect(visibleKeys).not.toContain("payment_history");
  });
});
