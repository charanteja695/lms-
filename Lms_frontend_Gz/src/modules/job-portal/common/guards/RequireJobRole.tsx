import { Navigate, Outlet } from "react-router-dom";

import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { PageLoader } from "@/shared/ui";

export type SupportedJobRole =
  | "super_admin"
  | "admin"
  | "institution_head"
  | "staff"
  | "student"
  | "employer_admin"
  | "recruiter";

interface RequireJobRoleProps {
  allowedRoles: SupportedJobRole[];
  redirectTo?: string;
}

/**
 * Route guard enforcing role-based access control across Job Portal modules.
 * Unauthorised users are automatically redirected to their role-specific landing page.
 */
export function RequireJobRole({ allowedRoles, redirectTo }: RequireJobRoleProps) {
  const { permissions, isLoading } = usePermissions();

  if (isLoading) return <PageLoader />;

  const role = permissions.role as SupportedJobRole;

  if (!allowedRoles.includes(role)) {
    const defaultRoute =
      role === "super_admin" || role === "admin"
        ? "/jobs/employer"
        : role === "institution_head" || role === "staff"
        ? "/jobs/institution"
        : role === "employer_admin" || role === "recruiter"
        ? "/jobs/employer"
        : "/jobs/board";

    return <Navigate to={redirectTo ?? defaultRoute} replace />;
  }

  return <Outlet />;
}
