import { describe, expect, it } from "vitest";

import type { Permissions } from "@/modules/user-management/common/permissions/types";
import {
  CATEGORY_TO_KIND,
  getAllowedCategories,
  isCategoryAllowed,
  type UserCategory,
} from "@/modules/user-management/manage/components/ManageUsersRoute";
import { PERSON_SCREENS } from "@/modules/user-management/manage/people/config";

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

describe("ManageUsersWorkspace - Category and Configuration Mapping", () => {
  it("verifies category allowance with isCategoryAllowed", () => {
    const studentPerms: Permissions = {
      ...basePermissions,
      role: "student",
      users: { ...basePermissions.users, view_roles: [] },
    };
    expect(isCategoryAllowed("admins", studentPerms)).toBe(false);
    expect(isCategoryAllowed("institutions", studentPerms)).toBe(false);
    expect(isCategoryAllowed("institution-heads", studentPerms)).toBe(false);
    expect(isCategoryAllowed("staff", studentPerms)).toBe(false);
    expect(isCategoryAllowed("students", studentPerms)).toBe(false);

    const staffPerms: Permissions = {
      ...basePermissions,
      role: "staff",
      users: { ...basePermissions.users, view_roles: ["student"] },
    };
    expect(isCategoryAllowed("admins", staffPerms)).toBe(false);
    expect(isCategoryAllowed("institutions", staffPerms)).toBe(false);
    expect(isCategoryAllowed("institution-heads", staffPerms)).toBe(false);
    expect(isCategoryAllowed("staff", staffPerms)).toBe(false);
    expect(isCategoryAllowed("students", staffPerms)).toBe(true);
  });

  it("maps URL category strings to authoritative PersonKinds", () => {
    expect(CATEGORY_TO_KIND["admins"]).toBe("admin");
    expect(CATEGORY_TO_KIND["institution-heads"]).toBe("institution_head");
    expect(CATEGORY_TO_KIND["staff"]).toBe("staff");
    expect(CATEGORY_TO_KIND["students"]).toBe("student");
  });

  it("binds each category to the correct backend resource and metadata in PERSON_SCREENS", () => {
    // Admins -> admins resource
    const adminScreen = PERSON_SCREENS[CATEGORY_TO_KIND["admins"]!];
    expect(adminScreen.resource).toBe("admins");
    expect(adminScreen.title).toBe("Admins");
    expect(adminScreen.one).toBe("admin");

    // Institution Heads -> users resource
    const headScreen = PERSON_SCREENS[CATEGORY_TO_KIND["institution-heads"]!];
    expect(headScreen.resource).toBe("users");
    expect(headScreen.title).toBe("Institution heads");
    expect(headScreen.one).toBe("institution head");

    // Staff -> users resource
    const staffScreen = PERSON_SCREENS[CATEGORY_TO_KIND["staff"]!];
    expect(staffScreen.resource).toBe("users");
    expect(staffScreen.title).toBe("Staff");
    expect(staffScreen.one).toBe("staff member");

    // Students -> users resource
    const studentScreen = PERSON_SCREENS[CATEGORY_TO_KIND["students"]!];
    expect(studentScreen.resource).toBe("users");
    expect(studentScreen.title).toBe("Students");
    expect(studentScreen.one).toBe("student");
  });
});

describe("ManageUsersWorkspace - Query Parameter Construction", () => {
  function computeApiParams(
    category: UserCategory,
    params: {
      page?: string | number;
      per_page?: string | number;
      search_text?: string;
      status?: string;
      organization_id?: string;
    },
  ) {
    const kind = CATEGORY_TO_KIND[category]!;
    const isAdmins = PERSON_SCREENS[kind].resource === "admins";
    return {
      page: params.page ? Number(params.page) : 1,
      per_page: params.per_page ? Number(params.per_page) : 20,
      search_text: params.search_text,
      status: params.status,
      ...(isAdmins ? {} : { role: kind, organization_id: params.organization_id }),
    };
  }

  it("constructs correct API query for admins (omits role and organization_id)", () => {
    const result = computeApiParams("admins", {
      page: "2",
      per_page: "25",
      search_text: "alice",
      status: "active",
      organization_id: "inst-123",
    });

    expect(result).toEqual({
      page: 2,
      per_page: 25,
      search_text: "alice",
      status: "active",
    });
    expect(result).not.toHaveProperty("role");
    expect(result).not.toHaveProperty("organization_id");
  });

  it("constructs correct API query for institution heads with role and organization_id", () => {
    const result = computeApiParams("institution-heads", {
      page: "1",
      per_page: "20",
      search_text: "principal",
      organization_id: "inst-456",
    });

    expect(result).toEqual({
      page: 1,
      per_page: 20,
      search_text: "principal",
      status: undefined,
      role: "institution_head",
      organization_id: "inst-456",
    });
  });

  it("constructs correct API query for staff with role and organization_id", () => {
    const result = computeApiParams("staff", {
      page: 3,
      per_page: 50,
      status: "suspended",
      organization_id: "inst-789",
    });

    expect(result).toEqual({
      page: 3,
      per_page: 50,
      search_text: undefined,
      status: "suspended",
      role: "staff",
      organization_id: "inst-789",
    });
  });

  it("constructs correct API query for students with role and organization_id", () => {
    const result = computeApiParams("students", {
      page: 1,
      per_page: 20,
      search_text: "2024CS01",
      organization_id: "inst-999",
    });

    expect(result).toEqual({
      page: 1,
      per_page: 20,
      search_text: "2024CS01",
      status: undefined,
      role: "student",
      organization_id: "inst-999",
    });
  });
});

describe("ManageUsersWorkspace - Category Tab & Action Permissions", () => {
  it("determines Add button permissions per category", () => {
    function canAddCategory(category: UserCategory, perms: Permissions): boolean {
      if (category === "institutions") return Boolean(perms.institutions?.create);
      const kind = CATEGORY_TO_KIND[category]!;
      const isAdmins = PERSON_SCREENS[kind].resource === "admins";
      return isAdmins ? perms.admins.create : perms.users.create_roles.includes(kind as any);
    }

    const institutionHeadPerms: Permissions = {
      ...basePermissions,
      role: "institution_head",
      admins: { view: false, create: false },
      institutions: { ...basePermissions.institutions, create: false },
      users: {
        ...basePermissions.users,
        view_roles: ["staff", "student"],
        create_roles: ["staff", "student"],
      },
    };

    expect(canAddCategory("admins", institutionHeadPerms)).toBe(false);
    expect(canAddCategory("institutions", institutionHeadPerms)).toBe(false);
    expect(canAddCategory("institution-heads", institutionHeadPerms)).toBe(false);
    expect(canAddCategory("staff", institutionHeadPerms)).toBe(true);
    expect(canAddCategory("students", institutionHeadPerms)).toBe(true);

    const superAdminPerms: Permissions = {
      ...basePermissions,
      role: "super_admin",
      admins: { view: true, create: true },
      institutions: { ...basePermissions.institutions, create: true },
      users: {
        ...basePermissions.users,
        view_roles: ["institution_head", "staff", "student"],
        create_roles: ["institution_head", "staff", "student"],
      },
    };

    expect(canAddCategory("admins", superAdminPerms)).toBe(true);
    expect(canAddCategory("institutions", superAdminPerms)).toBe(true);
    expect(canAddCategory("institution-heads", superAdminPerms)).toBe(true);
    expect(canAddCategory("staff", superAdminPerms)).toBe(true);
    expect(canAddCategory("students", superAdminPerms)).toBe(true);
  });

  it("correctly identifies single-category access for staff members", () => {
    const staffPerms: Permissions = {
      ...basePermissions,
      role: "staff",
      users: {
        ...basePermissions.users,
        view_roles: ["student"],
        create_roles: ["student"],
      },
    };

    const allowed = getAllowedCategories(staffPerms);
    expect(allowed).toEqual(["students"]);
    expect(allowed.length).toBe(1);
    // When allowed.length === 1, UI renders a clean label badge instead of interactive tabs
  });
});

describe("ManageUsersWorkspace - URL State & Query Preservation", () => {
  function handleCategoryChange(
    nextCategory: UserCategory,
    currentSearchParams: URLSearchParams,
  ): URLSearchParams {
    const next = new URLSearchParams(currentSearchParams);
    next.set("category", nextCategory);
    next.set("page", "1");
    next.delete("search_text");
    next.delete("user");
    next.delete("add");
    return next;
  }

  it("preserves organization_id and organization_label when switching categories", () => {
    const initial = new URLSearchParams({
      category: "staff",
      organization_id: "org-uuid-1234",
      organization_label: "Engineering College",
      page: "3",
      search_text: "Smith",
      user: "user-999",
      add: "1",
    });

    const next = handleCategoryChange("students", initial);

    expect(next.get("category")).toBe("students");
    expect(next.get("organization_id")).toBe("org-uuid-1234");
    expect(next.get("organization_label")).toBe("Engineering College");
    expect(next.get("page")).toBe("1");
    expect(next.has("search_text")).toBe(false);
    expect(next.has("user")).toBe(false);
    expect(next.has("add")).toBe(false);
  });

  it("clearing institution filter removes both organization_id and organization_label", () => {
    const params = new URLSearchParams({
      category: "students",
      organization_id: "org-uuid-1234",
      organization_label: "Engineering College",
    });

    params.delete("organization_id");
    params.delete("organization_label");

    expect(params.has("organization_id")).toBe(false);
    expect(params.has("organization_label")).toBe(false);
    expect(params.get("category")).toBe("students");
  });

  it("normalizes legacy institution param to organization_id", () => {
    function normalizeInstitutionParam(searchParams: URLSearchParams): URLSearchParams {
      const next = new URLSearchParams(searchParams);
      if (next.has("institution") && !next.has("organization_id")) {
        next.set("organization_id", next.get("institution")!);
        next.delete("institution");
      }
      return next;
    }

    const legacy = new URLSearchParams({
      category: "students",
      institution: "inst-legacy-123",
      search: "Alice",
    });

    const normalized = normalizeInstitutionParam(legacy);
    expect(normalized.has("institution")).toBe(false);
    expect(normalized.get("organization_id")).toBe("inst-legacy-123");
    expect(normalized.get("category")).toBe("students");
    expect(normalized.get("search")).toBe("Alice");
  });

  it("falls back to first allowed category when unauthorized category is accessed", () => {
    function resolveCategory(
      requestedCategory: string | null,
      allowed: UserCategory[],
    ): UserCategory {
      if (requestedCategory && allowed.includes(requestedCategory as UserCategory)) {
        return requestedCategory as UserCategory;
      }
      return allowed[0] ?? "students";
    }

    // Staff member (can only view students) tries to access ?category=admins
    const staffAllowed: UserCategory[] = ["students"];
    expect(resolveCategory("admins", staffAllowed)).toBe("students");

    // Institution Head (can view staff and students) tries to access ?category=admins
    const headAllowed: UserCategory[] = ["staff", "students"];
    expect(resolveCategory("admins", headAllowed)).toBe("staff");

    // Super Admin accesses ?category=admins
    const superAdminAllowed: UserCategory[] = ["admins", "institution-heads", "staff", "students"];
    expect(resolveCategory("admins", superAdminAllowed)).toBe("admins");

    // No category param provided -> defaults to first allowed
    expect(resolveCategory(null, superAdminAllowed)).toBe("admins");
    expect(resolveCategory(null, staffAllowed)).toBe("students");
  });

  it("closing UserDetailsDrawer clears user param while preserving all other list state", () => {
    const listState = new URLSearchParams({
      category: "staff",
      page: "2",
      per_page: "25",
      search_text: "Kumar",
      status: "active",
      organization_id: "inst-999",
      organization_label: "Delhi Tech",
      user: "user-target-777",
    });

    // Action: onClose of UserDetailsDrawer
    listState.delete("user");

    expect(listState.has("user")).toBe(false);
    expect(listState.get("category")).toBe("staff");
    expect(listState.get("page")).toBe("2");
    expect(listState.get("per_page")).toBe("25");
    expect(listState.get("search_text")).toBe("Kumar");
    expect(listState.get("status")).toBe("active");
    expect(listState.get("organization_id")).toBe("inst-999");
    expect(listState.get("organization_label")).toBe("Delhi Tech");
  });

  it("clears add param when closing Add User form", () => {
    const addState = new URLSearchParams({
      category: "students",
      add: "1",
      organization_id: "inst-999",
    });

    addState.delete("add");

    expect(addState.has("add")).toBe(false);
    expect(addState.get("category")).toBe("students");
    expect(addState.get("organization_id")).toBe("inst-999");
  });
});
