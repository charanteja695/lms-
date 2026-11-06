import { describe, it, expect, vi, beforeEach } from "vitest";
import { useJobRights } from "./useJobRights";

let mockRole: string = "super_admin";
let mockHeldPermissions: Set<string> = new Set();

vi.mock("@/modules/user-management/auth/hooks/useAuth", () => ({
  useAuth: () => ({ role: mockRole }),
}));

vi.mock("@/modules/user-management/common/permissions/useCan", () => ({
  useCan: () => ({
    can: (key: string) => mockRole === "super_admin" || mockHeldPermissions.has(key),
    acts: (cell: string, legacy: string) =>
      mockRole === "super_admin" || mockHeldPermissions.has(cell) || mockHeldPermissions.has(legacy),
    isSuperAdmin: mockRole === "super_admin",
  }),
}));

describe("useJobRights - Canonical Role & Careers Matrix Alignment", () => {
  beforeEach(() => {
    mockRole = "student";
    mockHeldPermissions = new Set();
  });

  describe("1. Super Admin", () => {
    it("has full global rights, exclusive hiring authority, and placement confirmation", () => {
      mockRole = "super_admin";
      const rights = useJobRights();

      expect(rights.isSuperAdmin).toBe(true);
      expect(rights.canPostJob).toBe(true);
      expect(rights.canEditJobs).toBe(true);
      expect(rights.runsHiring).toBe(true);
      expect(rights.canConfirmPlacement).toBe(true);
    });
  });

  describe("2. Admin", () => {
    it("can post and edit jobs globally, confirm placements, but CANNOT record hiring", () => {
      mockRole = "admin";
      mockHeldPermissions = new Set(["create_jobs", "edit_jobs", "confirm_placement"]);
      const rights = useJobRights();

      expect(rights.isAdmin).toBe(true);
      expect(rights.isSuperAdmin).toBe(false);
      expect(rights.canPostJob).toBe(true);
      expect(rights.canEditJobs).toBe(true);
      expect(rights.canConfirmPlacement).toBe(true);
      // Exclusive to Super Admin
      expect(rights.runsHiring).toBe(false);
    });
  });

  describe("3. Institution Head", () => {
    it("has posting and editing DISABLED by default", () => {
      mockRole = "institution_head";
      mockHeldPermissions = new Set(["view_applicants", "update_application_status"]);
      const rights = useJobRights();

      expect(rights.isInstitutionHead).toBe(true);
      expect(rights.canPostJob).toBe(false);
      expect(rights.canEditJobs).toBe(false);
      expect(rights.runsHiring).toBe(false);
      expect(rights.canConfirmPlacement).toBe(false);
    });

    it("enables canPostJob when create_jobs is granted without enabling edit_jobs", () => {
      mockRole = "institution_head";
      mockHeldPermissions = new Set(["create_jobs"]);
      const rights = useJobRights();

      expect(rights.canPostJob).toBe(true);
      // Enabling create_jobs must NOT enable edit_jobs
      expect(rights.canEditJobs).toBe(false);
      expect(rights.runsHiring).toBe(false);
      expect(rights.canConfirmPlacement).toBe(false);
    });

    it("enables canEditJobs when edit_jobs is granted without enabling create_jobs", () => {
      mockRole = "institution_head";
      mockHeldPermissions = new Set(["edit_jobs"]);
      const rights = useJobRights();

      // Enabling edit_jobs must NOT enable canPostJob
      expect(rights.canPostJob).toBe(false);
      expect(rights.canEditJobs).toBe(true);
      expect(rights.runsHiring).toBe(false);
      expect(rights.canConfirmPlacement).toBe(false);
    });
  });

  describe("4. Staff", () => {
    it("has Careers capabilities disabled by default", () => {
      mockRole = "staff";
      mockHeldPermissions = new Set();
      const rights = useJobRights();

      expect(rights.isStaff).toBe(true);
      expect(rights.canPostJob).toBe(false);
      expect(rights.canEditJobs).toBe(false);
      expect(rights.runsHiring).toBe(false);
      expect(rights.canConfirmPlacement).toBe(false);
    });

    it("allows posting only when create_jobs is explicitly granted to staff", () => {
      mockRole = "staff";
      mockHeldPermissions = new Set(["create_jobs"]);
      const rights = useJobRights();

      expect(rights.canPostJob).toBe(true);
      expect(rights.canEditJobs).toBe(false);
      expect(rights.canConfirmPlacement).toBe(false);
    });
  });

  describe("5. Student", () => {
    it("can only apply and withdraw, never administrative actions", () => {
      mockRole = "student";
      mockHeldPermissions = new Set(["jobs.view", "jobs.apply"]);
      const rights = useJobRights();

      expect(rights.isStudent).toBe(true);
      expect(rights.canApply).toBe(true);
      expect(rights.canWithdraw).toBe(true);
      expect(rights.canPostJob).toBe(false);
      expect(rights.canEditJobs).toBe(false);
      expect(rights.runsHiring).toBe(false);
      expect(rights.canConfirmPlacement).toBe(false);
    });
  });
});
