import { Navigate } from "react-router-dom";

import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";

/**
 * Role-aware default navigation for Job Portal:
 * - SUPER_ADMIN / ADMIN -> /jobs/employer (Manage Jobs)
 * - INSTITUTION_HEAD / STAFF -> /jobs/institution (Placements)
 * - EMPLOYER (employer_admin / recruiter) -> /jobs/employer (Manage Jobs)
 * - STUDENT -> /jobs/board (Find Jobs)
 */
export function JobPortalHomePage() {
  const rights = useJobRights();

  if (rights.isSuperAdmin || rights.isAdmin) {
    return <Navigate to="/jobs/employer" replace />;
  }
  if (rights.isHead || rights.isStaff || rights.isInstitution) {
    return <Navigate to="/jobs/institution" replace />;
  }
  if (rights.isEmployer) {
    return <Navigate to="/jobs/employer" replace />;
  }
  if (rights.isStudent) {
    return <Navigate to="/jobs/board" replace />;
  }
  return <Navigate to="/jobs/board" replace />;
}
