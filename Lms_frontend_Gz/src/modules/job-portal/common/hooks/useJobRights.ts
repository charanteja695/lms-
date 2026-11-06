import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";

/**
 * Evaluates role-based permissions and access rights for the Job Portal.
 * Accurately distinguishes students from administrators, institution staff, and employers.
 */
export function useJobRights() {
  const { can, holds, acts } = useCan();
  const { permissions } = usePermissions();
  const role = permissions.role;

  const isSuperAdmin = role === "super_admin";
  const isAdmin = role === "admin" || isSuperAdmin;
  const isStudent = role === "student";
  const isHead = role === "institution_head";
  const isStaff = role === "staff";
  const isInstitution = isHead || isStaff || permissions.organization_type === "institution" || acts("placements.view", "jobs.placements");
  const isEmployerAdmin = role === "employer_admin" || holds("jobs.company.manage");
  const isEmployer = role === "employer_admin" || role === "recruiter" || permissions.organization_type === "employer" || holds("jobs.hire");
  const isCareersManager = isSuperAdmin || can("careers.manage");

  return {
    isSuperAdmin,
    isAdmin,
    isStudent,
    canApply: isStudent && holds("jobs.apply"),
    canWithdraw: isStudent && holds("jobs.apply"),
    isEmployer,
    isEmployerAdmin,
    isInstitution,
    isHead,
    isStaff,
    isCareersManager,
    /** Posts jobs and runs hiring: a company's own team, or administrator / super admin. */
    runsHiring: isEmployer || isCareersManager || isAdmin,
    canCreateJob: isSuperAdmin || isAdmin || isEmployer,
  };
}
