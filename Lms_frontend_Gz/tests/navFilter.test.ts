import { describe, it, expect } from "vitest";
import { NAVIGATION } from "@/app/navigation";
import { getRoleDefaultPermissions } from "@/modules/user-management/common/permissions/usePermissions";

function resolveNavForRole(
  role: "super_admin" | "admin" | "institution_head" | "staff" | "student",
  customPerms?: string[],
) {
  const perms = getRoleDefaultPermissions(role);
  if (customPerms) {
    perms.permissions = [...perms.permissions, ...customPerms];
  }

  return NAVIGATION.filter((i) => {
    if (i.roles && !i.roles.includes(role)) return false;
    if (i.viewRole) return Boolean(perms?.users?.view_roles?.includes?.(i.viewRole));
    return i.menu ? perms.menu.includes(i.menu) : perms.sections.includes(i.section);
  }).map((item) => {
    let label = item.label;
    let to = item.to;
    let hint = item.hint;
    let icon = item.icon;

    if (item.roleOverrides?.[role]) {
      const override = item.roleOverrides[role]!;
      if (override.label) label = override.label;
      if (override.to) to = override.to;
      if (override.hint) hint = override.hint;
      if (override.icon) icon = override.icon;
    }

    let subItems = item.subItems;
    if (subItems) {
      subItems = subItems.filter((sub) => {
        if (sub.roles && !sub.roles.includes(role)) return false;
        if (sub.permission) {
          if (role === "super_admin") return true;
          const userPerms = perms.permissions ?? [];
          const hasPerm =
            userPerms.includes(sub.permission) ||
            userPerms.includes(`careers.${sub.permission}`) ||
            userPerms.includes("jobs.create");
          if (!hasPerm) return false;
        }
        return true;
      });
    }

    return {
      ...item,
      label,
      to,
      hint,
      icon,
      subItems,
    };
  });
}

describe("Minimal Careers & Placements Navigation Redesign", () => {
  it("verifies super_admin sees all 5 compact Careers items with global administrative capabilities", () => {
    const items = resolveNavForRole("super_admin");
    const careers = items.filter((i) => i.group === "careers");

    expect(careers.map((c) => c.label)).toEqual(["Overview", "Jobs", "Recruitment", "Placements", "More"]);

    const moreItem = careers.find((c) => c.label === "More")!;
    expect(moreItem.subItems?.map((s) => s.label)).toContain("Careers Roles & Permissions");
    expect(moreItem.subItems?.map((s) => s.label)).toContain("Hiring Companies");

    const recruitmentItem = careers.find((c) => c.label === "Recruitment")!;
    expect(recruitmentItem.subItems?.map((s) => s.label)).toContain("Interview Plans");

    const jobsItem = careers.find((c) => c.label === "Jobs")!;
    expect(jobsItem.subItems?.map((s) => s.label)).toContain("Post New Job");
  });

  it("verifies admin sees all 5 compact Careers items without Super Admin permissions settings", () => {
    const items = resolveNavForRole("admin");
    const careers = items.filter((i) => i.group === "careers");

    expect(careers.map((c) => c.label)).toEqual(["Overview", "Jobs", "Recruitment", "Placements", "More"]);

    const moreItem = careers.find((c) => c.label === "More")!;
    // Admin does NOT see Careers Roles & Permissions
    expect(moreItem.subItems?.map((s) => s.label)).not.toContain("Careers Roles & Permissions");
    expect(moreItem.subItems?.map((s) => s.label)).toContain("Hiring Companies");

    const recruitmentItem = careers.find((c) => c.label === "Recruitment")!;
    expect(recruitmentItem.subItems?.map((s) => s.label)).not.toContain("Interview Plans");

    const jobsItem = careers.find((c) => c.label === "Jobs")!;
    // Admin has create_jobs enabled by default
    expect(jobsItem.subItems?.map((s) => s.label)).toContain("Post New Job");
  });

  it("verifies institution_head has Post Job hidden by default and shown only when create_jobs is enabled", () => {
    // 1. By default: create_jobs is FALSE for institution_head
    const defaultItems = resolveNavForRole("institution_head");
    const defaultJobsItem = defaultItems.find((i) => i.group === "careers" && i.label === "Jobs")!;
    expect(defaultJobsItem.subItems?.map((s) => s.label)).toContain("Institution Jobs");
    expect(defaultJobsItem.subItems?.map((s) => s.label)).not.toContain("Post New Job");

    // 2. When create_jobs permission is enabled: Post New Job appears
    const withCreateJobs = resolveNavForRole("institution_head", ["create_jobs"]);
    const enabledJobsItem = withCreateJobs.find((i) => i.group === "careers" && i.label === "Jobs")!;
    expect(enabledJobsItem.subItems?.map((s) => s.label)).toContain("Post New Job");

    // 3. Enabling edit_jobs alone must NOT enable Post New Job
    const withEditOnly = resolveNavForRole("institution_head", ["edit_jobs"]);
    const editOnlyJobsItem = withEditOnly.find((i) => i.group === "careers" && i.label === "Jobs")!;
    expect(editOnlyJobsItem.subItems?.map((s) => s.label)).not.toContain("Post New Job");
  });

  it("verifies institution_head sees all 5 compact Careers items scoped to institution", () => {
    const items = resolveNavForRole("institution_head");
    const careers = items.filter((i) => i.group === "careers");

    expect(careers.map((c) => c.label)).toEqual(["Overview", "Jobs", "Recruitment", "Placements", "More"]);

    const jobsItem = careers.find((c) => c.label === "Jobs")!;
    expect(jobsItem.subItems?.map((s) => s.label)).toContain("Institution Jobs");
    expect(jobsItem.subItems?.map((s) => s.label)).not.toContain("Manage Jobs");

    const moreItem = careers.find((c) => c.label === "More")!;
    expect(moreItem.to).toBe("/career/students");
    expect(moreItem.subItems?.map((s) => s.label)).not.toContain("Careers Roles & Permissions");
  });

  it("verifies staff has Careers navigation hidden by default", () => {
    const items = resolveNavForRole("staff");
    const careers = items.filter((i) => i.group === "careers");

    // Hidden by default for staff
    expect(careers.length).toBe(0);
  });

  it("verifies student sees 5 student-tailored compact items with simpler labels and no administrative controls", () => {
    const items = resolveNavForRole("student");
    const careers = items.filter((i) => i.group === "careers");

    expect(careers.map((c) => c.label)).toEqual(["Overview", "Jobs", "My Applications", "My Placement", "Resumes"]);

    // Verify destinations
    const overview = careers.find((c) => c.label === "Overview")!;
    expect(overview.to).toBe("/career");

    const jobs = careers.find((c) => c.label === "Jobs")!;
    expect(jobs.to).toBe("/jobs/board");

    const myApps = careers.find((c) => c.label === "My Applications")!;
    expect(myApps.to).toBe("/jobs/applications");

    const myPlacements = careers.find((c) => c.label === "My Placement")!;
    expect(myPlacements.to).toBe("/jobs/drives");

    const resumes = careers.find((c) => c.label === "Resumes")!;
    expect(resumes.to).toBe("/career/resumes");

    // Verify no administrative actions exposed to student
    const allStudentSubLabels = careers.flatMap((c) => c.subItems?.map((s) => s.label) ?? []);
    expect(allStudentSubLabels).not.toContain("Manage Jobs");
    expect(allStudentSubLabels).not.toContain("Post New Job");
    expect(allStudentSubLabels).not.toContain("Applicants & Pipeline");
    expect(allStudentSubLabels).not.toContain("Careers Roles & Permissions");
    expect(allStudentSubLabels).not.toContain("Interview Plans");
  });

  it("verifies learning paths is completely removed and my organization is hidden for student", () => {
    const allLabels = NAVIGATION.map((n) => n.label.toLowerCase());
    expect(allLabels.some((l) => l.includes("learning path"))).toBe(false);

    const studentItems = resolveNavForRole("student");
    expect(studentItems.some((i) => i.to === "/organization" || i.label.toLowerCase().includes("organization"))).toBe(false);
  });

  describe("System-Wide RBAC Dynamic Nav & Permission Enforcement", () => {
    it("dynamically hides AI Tutor when unchecked for student", () => {
      // By default student has ai_tutor in menu
      const defaultStudentNav = resolveNavForRole("student");
      expect(defaultStudentNav.some((i) => i.to === "/tutor" || i.label.toLowerCase().includes("tutor"))).toBe(true);

      // When ai_tutor is revoked by Super Admin
      const perms = getRoleDefaultPermissions("student");
      perms.menu = perms.menu.filter((m) => m !== "ai_tutor");
      perms.sections = perms.sections.filter((s) => s !== "ai_tutor");

      const filteredNav = NAVIGATION.filter((i) => {
        if (i.roles && !i.roles.includes("student")) return false;
        return i.menu ? perms.menu.includes(i.menu) : perms.sections.includes(i.section);
      });

      expect(filteredNav.some((i) => i.to === "/tutor" || i.label.toLowerCase().includes("tutor"))).toBe(false);
    });

    it("dynamically hides Certificates when unchecked for student", () => {
      const defaultStudentNav = resolveNavForRole("student");
      expect(defaultStudentNav.some((i) => i.to === "/certificates")).toBe(true);

      // When certificates is revoked
      const perms = getRoleDefaultPermissions("student");
      perms.menu = perms.menu.filter((m) => m !== "certificates");
      perms.sections = perms.sections.filter((s) => s !== "certificates");

      const filteredNav = NAVIGATION.filter((i) => {
        if (i.roles && !i.roles.includes("student")) return false;
        return i.menu ? perms.menu.includes(i.menu) : perms.sections.includes(i.section);
      });

      expect(filteredNav.some((i) => i.to === "/certificates")).toBe(false);
    });

    it("dynamically hides Exams & Certifications nav group when all its children are unchecked", () => {
      const perms = getRoleDefaultPermissions("student");
      // Remove all exams group entries (tests, certificates, proctoring)
      perms.menu = perms.menu.filter((m) => !["my_tests", "certificates", "proctoring"].includes(m));
      perms.sections = perms.sections.filter((s) => !["assessments", "certificates", "proctoring"].includes(s));

      const filteredNav = NAVIGATION.filter((i) => {
        if (i.roles && !i.roles.includes("student")) return false;
        return i.menu ? perms.menu.includes(i.menu) : perms.sections.includes(i.section);
      });

      const examsGroupEntries = filteredNav.filter((i) => i.group === "exams");
      expect(examsGroupEntries.length).toBe(0);
    });

    it("verifies permissions enforcement across all 5 canonical roles", () => {
      const roles: ("super_admin" | "admin" | "institution_head" | "staff" | "student")[] = [
        "super_admin",
        "admin",
        "institution_head",
        "staff",
        "student",
      ];

      for (const role of roles) {
        const perms = getRoleDefaultPermissions(role);
        expect(perms).toBeDefined();
        expect(perms.role).toBe(role);
        expect(Array.isArray(perms.sections)).toBe(true);
        expect(Array.isArray(perms.menu)).toBe(true);

        const nav = resolveNavForRole(role);
        expect(nav.length).toBeGreaterThan(0);
      }
    });
  });
});
