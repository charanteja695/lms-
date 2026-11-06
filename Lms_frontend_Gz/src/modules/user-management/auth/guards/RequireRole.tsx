import type { ReactNode } from "react";
import { Navigate, Outlet } from "react-router-dom";
import type { Role } from "@/modules/user-management/common/types";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { PageLoader } from "@/shared/ui";
import { AccessDeniedPage } from "@/shared/pages/AccessDeniedPage";

export interface RequireRoleProps {
  roles: Role[];
  redirectTo?: string;
  studentRedirect?: string;
  children?: ReactNode;
}

/**
 * Enforces role-based route access.
 * If user does not have an allowed role:
 * 1. If user is student and studentRedirect is provided, redirect to studentRedirect.
 * 2. If redirectTo is provided, redirect to redirectTo.
 * 3. Otherwise, render the standard AccessDeniedPage (HTTP 403).
 */
export function RequireRole({
  roles,
  redirectTo,
  studentRedirect,
  children,
}: RequireRoleProps) {
  const { isLoading, permissions } = usePermissions();

  if (isLoading) {
    return <PageLoader />;
  }

  const userRole = permissions.role as Role;
  const isAllowed = roles.includes(userRole);

  if (isAllowed) {
    return children ? <>{children}</> : <Outlet />;
  }

  if (userRole === "student" && studentRedirect) {
    return <Navigate to={studentRedirect} replace />;
  }

  if (redirectTo) {
    return <Navigate to={redirectTo} replace />;
  }

  return (
    <AccessDeniedPage
      title="Access Denied"
      message={`Your role (${userRole.replace("_", " ")}) does not have permission to access this page.`}
    />
  );
}
