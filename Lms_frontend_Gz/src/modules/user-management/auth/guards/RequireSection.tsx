import { Navigate, Outlet } from "react-router-dom";

import type { Section } from "@/modules/user-management/common/permissions/types";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { PageLoader } from "@/shared/ui";

/**
 * Shows a screen only if the server lists its section for this person. It is a navigation aid:
 * the API authorises every request regardless.
 */
export function RequireSection({ section }: { section: Section }) {
  const { isLoading, can } = usePermissions();
  if (isLoading) return <PageLoader />;
  return can(section) ? <Outlet /> : <Navigate to="/" replace />;
}
