import { Navigate, Outlet } from "react-router-dom";

import type { ManagedRole } from "@/modules/user-management/common/types";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { PageLoader } from "@/shared/ui";

/** Opens a people screen only for someone the server lets see that role (`permissions.users.view_roles`). */
export function RequirePeopleRole({ role }: { role: ManagedRole }) {
  const { isLoading, permissions } = usePermissions();
  if (isLoading) return <PageLoader />;
  return permissions.users.view_roles.includes(role) ? <Outlet /> : <Navigate to="/" replace />;
}
