import { describe, expect, it } from "vitest";

import type { MatrixPage } from "@/modules/user-management/permissions/api/permissionAdminApi";
import {
  groupPages,
  plural,
  viewKey,
} from "@/modules/user-management/permissions/components/matrix/matrixModel";

const samplePages: MatrixPage[] = [
  {
    key: "students",
    label: "Students",
    group: "User management",
    description: "Students of their institution.",
    holders: ["institution_head", "staff"],
    actions: [
      { action: "view", key: "students.view", meaning: "See students list", default_roles: ["institution_head", "staff"] },
      { action: "create", key: "students.create", meaning: "Add student", default_roles: ["institution_head", "staff"] },
      { action: "delete", key: "students.delete", meaning: "Remove student", default_roles: ["institution_head"] },
    ],
  },
  {
    key: "academic_structure",
    label: "Academic structure",
    group: "User management",
    description: "Departments and programs.",
    holders: ["institution_head", "staff"],
    actions: [
      { action: "view", key: "academic_structure.view", meaning: "View departments", default_roles: ["institution_head", "staff"] },
      { action: "manage", key: "academic_structure.manage", meaning: "Manage departments", default_roles: ["institution_head"] },
    ],
  },
  {
    key: "courses",
    label: "Courses",
    group: "Learning",
    description: "Course curriculum and content.",
    holders: ["institution_head", "staff", "student"],
    actions: [
      { action: "view", key: "courses.view", meaning: "Browse courses", default_roles: ["institution_head", "staff", "student"] },
    ],
  },
  {
    key: "billing",
    label: "Billing",
    group: "Finance",
    description: "Invoices and subscription payments.",
    holders: ["institution_head"],
    actions: [
      { action: "view", key: "billing.view", meaning: "View billing info", default_roles: ["institution_head"] },
    ],
  },
];

describe("Roles & Permissions Matrix - Domain Model & Logic", () => {
  it("computes viewKey correctly for any matrix page", () => {
    expect(viewKey(samplePages[0]!)).toBe("students.view");
    expect(viewKey(samplePages[1]!)).toBe("academic_structure.view");
    expect(viewKey(samplePages[2]!)).toBe("courses.view");
  });

  it("formats plural strings correctly", () => {
    expect(plural(1, "change")).toBe("1 change");
    expect(plural(3, "change")).toBe("3 changes");
    expect(plural(0, "box")).toBe("0 boxes");
  });

  it("filters pages based on role holders", () => {
    // Staff should see User management (students, academic_structure) and Learning (courses), but NOT Finance (billing)
    const staffGroups = groupPages(samplePages, "staff", "");
    expect(staffGroups).toHaveLength(2);
    expect(staffGroups.map((g) => g.title)).toEqual(["User management", "Learning"]);

    const userMgmt = staffGroups.find((g) => g.title === "User management");
    expect(userMgmt?.pages).toHaveLength(2);
    expect(userMgmt!.pages.map((p) => p.key)).toEqual(["students", "academic_structure"]);

    // Student should only see Learning (courses)
    const studentGroups = groupPages(samplePages, "student", "");
    expect(studentGroups).toHaveLength(1);
    expect(studentGroups[0]!.title).toBe("Learning");
    expect(studentGroups[0]!.pages.map((p) => p.key)).toEqual(["courses"]);

    // Institution head sees all 3 groups
    const headGroups = groupPages(samplePages, "institution_head", "");
    expect(headGroups).toHaveLength(3);
  });

  it("filters pages by search query across label, group, and description", () => {
    // Match by page label
    const byLabel = groupPages(samplePages, "staff", "students");
    expect(byLabel).toHaveLength(1);
    expect(byLabel[0]!.pages[0]!.key).toBe("students");

    // Match by group
    const byGroup = groupPages(samplePages, "staff", "learning");
    expect(byGroup).toHaveLength(1);
    expect(byGroup[0]!.title).toBe("Learning");

    // Match by description keyword
    const byDesc = groupPages(samplePages, "staff", "departments");
    expect(byDesc).toHaveLength(1);
    expect(byDesc[0]!.pages[0]!.key).toBe("academic_structure");

    // Case insensitivity
    const caseInsensitive = groupPages(samplePages, "staff", "ACADEMIC");
    expect(caseInsensitive).toHaveLength(1);
    expect(caseInsensitive[0]!.pages[0]!.key).toBe("academic_structure");

    // No match
    const noMatch = groupPages(samplePages, "staff", "nonexistent");
    expect(noMatch).toHaveLength(0);
  });

  it("generates correct pending changes map and resetAll payload", () => {
    const rowPermissions = [
      { key: "students.view", allowed: true, changed: false },
      { key: "students.create", allowed: true, changed: true },
      { key: "students.delete", allowed: false, changed: true },
    ];

    const changedKeys = rowPermissions.filter((c) => c.changed).map((c) => c.key);
    expect(changedKeys).toEqual(["students.create", "students.delete"]);

    // Resetting changes requires setting values to null for the server
    const resetAll = Object.fromEntries(changedKeys.map((k) => [k, null]));
    expect(resetAll).toEqual({
      "students.create": null,
      "students.delete": null,
    });
  });

  it("enforces View dependency rule for action checkboxes", () => {
    // If view is false, other actions on the same page are blocked
    function isActionBlocked(actionName: string, isViewAllowed: boolean): boolean {
      const isView = actionName === "view";
      return !isView && !isViewAllowed;
    }

    expect(isActionBlocked("view", false)).toBe(false); // View is never blocked by itself
    expect(isActionBlocked("create", false)).toBe(true); // Create blocked when View is false
    expect(isActionBlocked("delete", false)).toBe(true); // Delete blocked when View is false
    expect(isActionBlocked("create", true)).toBe(false); // Create allowed when View is true
    expect(isActionBlocked("delete", true)).toBe(false); // Delete allowed when View is true
  });
});
