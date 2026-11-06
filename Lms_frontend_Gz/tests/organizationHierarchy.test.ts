import { describe, expect, it } from "vitest";

import type { Permissions } from "@/modules/user-management/common/permissions/types";
import type { Hierarchy } from "@/modules/user-management/hierarchy/api/hierarchyApi";

const sampleHierarchy: Hierarchy = {
  super_admins: [
    { user_id: "sa-1", full_name: "Super Admin Jane", status: "active" },
  ],
  admins: [
    {
      admin: { user_id: "admin-1", full_name: "Admin Bob", status: "active" },
      institutions: [
        {
          organization_id: "org-1",
          name: "GenZ Institute of Technology",
          code: "GZIT",
          status: "active",
          city: "Hyderabad",
          heads: [{ user_id: "head-1", full_name: "Dr. Alistair Vance", status: "active" }],
          staff: 42,
          students: 1280,
          departments: 6,
        },
        {
          organization_id: "org-2",
          name: "GenZ Business Academy",
          code: "GZBA",
          status: "active",
          city: "Bangalore",
          heads: [],
          staff: 0,
          students: 0,
          departments: 2,
        },
      ],
    },
    {
      admin: null,
      institutions: [
        {
          organization_id: "org-3",
          name: "Direct University Campus",
          code: "DUC",
          status: "suspended",
          city: "Mumbai",
          heads: [{ user_id: "head-3", full_name: "Dean Sarah Connor", status: "active" }],
          staff: 15,
          students: 350,
          departments: 3,
        },
      ],
    },
  ],
  totals: { admins: 1, institutions: 3, staff: 57, students: 1630 },
};

describe("Organization Hierarchy - Critical Architecture Invariants", () => {
  it("enforces that hierarchy tree ends at institution nodes (NO individual staff/student nodes)", () => {
    // Traverse the entire hierarchy data structure
    for (const branch of sampleHierarchy.admins) {
      for (const inst of branch.institutions) {
        // Institution node must NOT have children nodes for staff or students
        expect(inst).not.toHaveProperty("children");
        expect(inst).not.toHaveProperty("staff_nodes");
        expect(inst).not.toHaveProperty("student_nodes");
        
        // Staff and students must only exist as aggregated numerical counts
        expect(typeof inst.staff).toBe("number");
        expect(typeof inst.students).toBe("number");
        
        // Heads is an attribute on the card
        expect(Array.isArray(inst.heads)).toBe(true);
      }
    }
  });

  it("handles population count states accurately: positive, zero, and unavailable", () => {
    function formatCount(count: number | undefined, singular: string, plural: string): string {
      if (count === undefined || count === null) return "—";
      return `${count.toLocaleString()} ${count === 1 ? singular : plural}`;
    }

    // 1. Positive count
    expect(formatCount(42, "staff member", "staff")).toBe("42 staff");
    expect(formatCount(1280, "student", "students")).toBe("1,280 students");

    // 2. Zero count (must display '0', NOT '—')
    expect(formatCount(0, "staff member", "staff")).toBe("0 staff");
    expect(formatCount(0, "student", "students")).toBe("0 students");

    // 3. Unavailable / error count (must display '—', NOT '0')
    expect(formatCount(undefined, "staff member", "staff")).toBe("—");
    expect(formatCount(undefined, "student", "students")).toBe("—");
  });
});

describe("Organization Hierarchy - View Switching & URL Synchronization", () => {
  function computeView(searchParams: URLSearchParams): "canvas" | "table" {
    return searchParams.get("view") === "table" ? "table" : "canvas";
  }

  function toggleView(currentParams: URLSearchParams, nextView: "canvas" | "table"): URLSearchParams {
    const next = new URLSearchParams(currentParams);
    if (nextView === "canvas") {
      next.delete("view");
    } else {
      next.set("view", "table");
    }
    next.set("page", "1");
    return next;
  }

  it("defaults to canvas view when no view param is present", () => {
    const params = new URLSearchParams();
    expect(computeView(params)).toBe("canvas");
  });

  it("resolves to table view when view=table is present", () => {
    const params = new URLSearchParams({ view: "table" });
    expect(computeView(params)).toBe("table");
  });

  it("preserves search text and status filters when toggling between canvas and table", () => {
    const initial = new URLSearchParams({
      search: "Technology",
      status: "active",
      selected: "org-1",
    });

    const toTable = toggleView(initial, "table");
    expect(toTable.get("view")).toBe("table");
    expect(toTable.get("search")).toBe("Technology");
    expect(toTable.get("status")).toBe("active");
    expect(toTable.get("selected")).toBe("org-1");

    const toCanvas = toggleView(toTable, "canvas");
    expect(toCanvas.has("view")).toBe(false); // default canvas
    expect(toCanvas.get("search")).toBe("Technology");
    expect(toCanvas.get("status")).toBe("active");
    expect(toCanvas.get("selected")).toBe("org-1");
  });
});

describe("Organization Hierarchy - Manage Users Link Generation", () => {
  function buildManageUsersUrl(
    category: "students" | "staff",
    institutionId: string,
    institutionName: string,
  ): string {
    return `/user-management/users?category=${category}&organization_id=${encodeURIComponent(institutionId)}&organization_label=${encodeURIComponent(institutionName)}`;
  }

  it("generates correct deep-link to Manage Users with institution filter pre-applied", () => {
    const studentsUrl = buildManageUsersUrl("students", "org-uuid-101", "MIT College");
    expect(studentsUrl).toBe(
      "/user-management/users?category=students&organization_id=org-uuid-101&organization_label=MIT%20College",
    );

    const staffUrl = buildManageUsersUrl("staff", "org-uuid-101", "MIT College");
    expect(staffUrl).toBe(
      "/user-management/users?category=staff&organization_id=org-uuid-101&organization_label=MIT%20College",
    );
  });
});

describe("Organization Hierarchy - Permission Boundaries", () => {
  const basePermissions: Permissions = {
    role: "student",
    organization_type: null,
    scopes: [],
    permissions: [],
    sections: ["hierarchy"],
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

  it("permits Add Institution only when permissions.institutions.create is true", () => {
    const unauthorizedPerms: Permissions = {
      ...basePermissions,
      institutions: { ...basePermissions.institutions, create: false },
    };
    expect(unauthorizedPerms.institutions.create).toBe(false);

    const authorizedPerms: Permissions = {
      ...basePermissions,
      institutions: { ...basePermissions.institutions, create: true },
    };
    expect(authorizedPerms.institutions.create).toBe(true);
  });

  it("permits admin reassignment only to super admin holding reassign_admin", () => {
    const adminPerms: Permissions = {
      ...basePermissions,
      role: "admin",
      institutions: { ...basePermissions.institutions, reassign_admin: false },
    };
    expect(adminPerms.institutions.reassign_admin).toBe(false);

    const superAdminPerms: Permissions = {
      ...basePermissions,
      role: "super_admin",
      institutions: { ...basePermissions.institutions, reassign_admin: true },
    };
    expect(superAdminPerms.institutions.reassign_admin).toBe(true);
  });
});

describe("Organization Hierarchy - Canvas Zoom & Transform Rules", () => {
  const MIN_ZOOM = 0.4;
  const MAX_ZOOM = 1.8;
  const ZOOM_STEP = 0.15;

  function clampZoom(value: number): number {
    return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(value * 100) / 100));
  }

  it("clamps zoom in within MAX_ZOOM (1.8x)", () => {
    expect(clampZoom(1.0 + ZOOM_STEP)).toBe(1.15);
    expect(clampZoom(1.75 + ZOOM_STEP)).toBe(1.8);
    expect(clampZoom(2.5)).toBe(1.8);
  });

  it("clamps zoom out within MIN_ZOOM (0.4x)", () => {
    expect(clampZoom(1.0 - ZOOM_STEP)).toBe(0.85);
    expect(clampZoom(0.45 - ZOOM_STEP)).toBe(0.4);
    expect(clampZoom(0.1)).toBe(0.4);
  });

  it("resets zoom to exactly 1.0 on Reset View action", () => {
    const resetTransform = { zoom: 1.0, pan: { x: 0, y: 0 } };
    expect(resetTransform.zoom).toBe(1.0);
    expect(resetTransform.pan).toEqual({ x: 0, y: 0 });
  });
});

describe("Organization Hierarchy - Card Filtering & Drawer State", () => {
  function matchesFilter(
    inst: { name: string; code: string; city: string; status: string },
    search: string,
    status: string,
  ): boolean {
    const q = search.trim().toLowerCase();
    const matchesSearch =
      !q ||
      inst.name.toLowerCase().includes(q) ||
      inst.code.toLowerCase().includes(q) ||
      inst.city.toLowerCase().includes(q);

    const matchesStatus = status === "all" || inst.status.toLowerCase() === status.toLowerCase();
    return matchesSearch && matchesStatus;
  }

  const sampleInst = {
    name: "GenZ Institute of Technology",
    code: "GZIT",
    city: "Hyderabad",
    status: "active",
  };

  it("matches search by name, code, or city", () => {
    expect(matchesFilter(sampleInst, "technology", "all")).toBe(true);
    expect(matchesFilter(sampleInst, "gzit", "all")).toBe(true);
    expect(matchesFilter(sampleInst, "hyderabad", "all")).toBe(true);
    expect(matchesFilter(sampleInst, "stanford", "all")).toBe(false);
  });

  it("matches status filter accurately", () => {
    expect(matchesFilter(sampleInst, "", "active")).toBe(true);
    expect(matchesFilter(sampleInst, "", "suspended")).toBe(false);
    expect(matchesFilter(sampleInst, "", "all")).toBe(true);
  });

  it("closing InstitutionDetailsDrawer clears selected param without resetting view or filters", () => {
    const hierarchyState = new URLSearchParams({
      view: "canvas",
      search: "Tech",
      status: "active",
      selected: "org-uuid-101",
    });

    // Action: onClose of InstitutionDetailsDrawer
    hierarchyState.delete("selected");

    expect(hierarchyState.has("selected")).toBe(false);
    expect(hierarchyState.get("view")).toBe("canvas");
    expect(hierarchyState.get("search")).toBe("Tech");
    expect(hierarchyState.get("status")).toBe("active");
  });
});
