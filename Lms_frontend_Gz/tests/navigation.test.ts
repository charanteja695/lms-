import { describe, expect, it } from "vitest";

import { computeRedirectUrl } from "@/shared/routing/RedirectWithQuery";
import { userManagementNavigation } from "@/modules/user-management/navigation";
import {
  getAllowedCategories,
  isCategoryAllowed,
} from "@/modules/user-management/manage/components/ManageUsersRoute";
import type { Permissions } from "@/modules/user-management/common/permissions/types";

describe("User Management Phase 1 Navigation", () => {
  it("contains exactly Manage users under the users group and removes hierarchy", () => {
    const userGroupItems = userManagementNavigation.filter((item) => item.group === "users");
    
    expect(userGroupItems).toHaveLength(1);
    
    const paths = userGroupItems.map((item) => item.to);
    expect(paths).toContain("/user-management/users");
    expect(paths).not.toContain("/user-management/hierarchy");

    // Ensure legacy routes are completely removed from sidebar
    expect(paths).not.toContain("/admins");
    expect(paths).not.toContain("/institutions");
    expect(paths).not.toContain("/institution-heads");
    expect(paths).not.toContain("/staff");
    expect(paths).not.toContain("/students");
    expect(paths).not.toContain("/organisation");
  });

  it("assigns the correct sections and metadata to Manage users destination", () => {
    const usersItem = userManagementNavigation.find((i) => i.to === "/user-management/users");
    expect(usersItem).toBeDefined();
    expect(usersItem?.section).toBe("users");
    expect(usersItem?.icon).toBe("users");
    expect(usersItem?.label).toBe("Manage users");

    const hierarchyItem = userManagementNavigation.find((i) => i.to === "/user-management/hierarchy");
    expect(hierarchyItem).toBeUndefined();
  });
});

describe("ManageUsersRoute category authorization", () => {
  const basePermissions: Permissions = {
    role: "student",
    organization_type: null,
    scopes: [],
    permissions: [],
    sections: [],
    menu: [],
    users: {
      view_roles: [],
      create_roles: [],
      can_import: false,
      can_export: false,
      filter_statuses: [],
      filter_by_institution: false,
    },
    admins: { view: false, create: false },
    institutions: { create: false, export: false, filter_statuses: [], filter_by_admin: false, reassign_admin: false },
    employers: { create: false, export: false, filter_statuses: [], filter_by_admin: false, reassign_admin: false },
    admin_scopes: [],
    audit_logs: { view: false },
    academics: { view: false, manage: false },
  };

  it("grants all five categories to super_admin", () => {
    const superAdminPerms: Permissions = {
      ...basePermissions,
      role: "super_admin",
      sections: ["users", "institutions", "admins"],
      admins: { view: true, create: true },
      institutions: { ...basePermissions.institutions, create: true },
      users: {
        ...basePermissions.users,
        view_roles: ["institution_head", "staff", "student"],
      },
    };

    expect(isCategoryAllowed("admins", superAdminPerms)).toBe(true);
    expect(isCategoryAllowed("institutions", superAdminPerms)).toBe(true);
    expect(isCategoryAllowed("institution-heads", superAdminPerms)).toBe(true);
    expect(isCategoryAllowed("staff", superAdminPerms)).toBe(true);
    expect(isCategoryAllowed("students", superAdminPerms)).toBe(true);
    expect(getAllowedCategories(superAdminPerms)).toEqual([
      "admins",
      "institutions",
      "institution-heads",
      "staff",
      "students",
    ]);
  });

  it("grants institutions, institution heads, staff, and students to admin (no admins tab)", () => {
    const adminPerms: Permissions = {
      ...basePermissions,
      role: "admin",
      sections: ["users", "institutions"],
      admins: { view: false, create: false },
      institutions: { ...basePermissions.institutions, create: true },
      users: {
        ...basePermissions.users,
        view_roles: ["institution_head", "staff", "student"],
      },
    };

    expect(isCategoryAllowed("admins", adminPerms)).toBe(false);
    expect(isCategoryAllowed("institutions", adminPerms)).toBe(true);
    expect(isCategoryAllowed("institution-heads", adminPerms)).toBe(true);
    expect(isCategoryAllowed("staff", adminPerms)).toBe(true);
    expect(isCategoryAllowed("students", adminPerms)).toBe(true);
    expect(getAllowedCategories(adminPerms)).toEqual([
      "institutions",
      "institution-heads",
      "staff",
      "students",
    ]);
  });

  it("grants staff and students only to institution_head", () => {
    const headPerms: Permissions = {
      ...basePermissions,
      role: "institution_head",
      admins: { view: false, create: false },
      users: {
        ...basePermissions.users,
        view_roles: ["staff", "student"],
      },
    };

    expect(isCategoryAllowed("admins", headPerms)).toBe(false);
    expect(isCategoryAllowed("institutions", headPerms)).toBe(false);
    expect(isCategoryAllowed("institution-heads", headPerms)).toBe(false);
    expect(isCategoryAllowed("staff", headPerms)).toBe(true);
    expect(isCategoryAllowed("students", headPerms)).toBe(true);
    expect(getAllowedCategories(headPerms)).toEqual(["staff", "students"]);
  });

  it("grants students only to staff with student view permission", () => {
    const staffPerms: Permissions = {
      ...basePermissions,
      role: "staff",
      admins: { view: false, create: false },
      users: {
        ...basePermissions.users,
        view_roles: ["student"],
      },
    };

    expect(isCategoryAllowed("admins", staffPerms)).toBe(false);
    expect(isCategoryAllowed("institutions", staffPerms)).toBe(false);
    expect(isCategoryAllowed("institution-heads", staffPerms)).toBe(false);
    expect(isCategoryAllowed("staff", staffPerms)).toBe(false);
    expect(isCategoryAllowed("students", staffPerms)).toBe(true);
    expect(getAllowedCategories(staffPerms)).toEqual(["students"]);
  });

  it("grants no categories to student", () => {
    expect(getAllowedCategories(basePermissions)).toEqual([]);
  });
});

describe("Legacy Route Redirection Mapping", () => {
  it("redirects /organisation to /user-management/users?category=institutions", () => {
    expect(
      computeRedirectUrl("", "/user-management/users", { category: "institutions" })
    ).toBe("/user-management/users?category=institutions");
  });

  it("redirects /institutions to /user-management/users?category=institutions preserving params", () => {
    expect(
      computeRedirectUrl("?status=active&search_text=college", "/user-management/users", {
        category: "institutions",
      })
    ).toBe("/user-management/users?status=active&search_text=college&category=institutions");
  });

  it("redirects /admins to /user-management/users?category=admins preserving params", () => {
    expect(
      computeRedirectUrl("?page=2", "/user-management/users", { category: "admins" })
    ).toBe("/user-management/users?page=2&category=admins");
  });

  it("redirects /institution-heads to /user-management/users?category=institution-heads preserving institution filter", () => {
    expect(
      computeRedirectUrl("?organization_id=123", "/user-management/users", {
        category: "institution-heads",
      })
    ).toBe("/user-management/users?organization_id=123&category=institution-heads");
  });

  it("redirects /staff to /user-management/users?category=staff", () => {
    expect(
      computeRedirectUrl("", "/user-management/users", { category: "staff" })
    ).toBe("/user-management/users?category=staff");
  });

  it("redirects /students to /user-management/users?category=students preserving query params", () => {
    expect(
      computeRedirectUrl("?program=BTech", "/user-management/users", {
        category: "students",
      })
    ).toBe("/user-management/users?program=BTech&category=students");
  });
});
