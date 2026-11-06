import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const RolePermissionsPage = lazyNamed(() => import("./pages/RolePermissionsPage"), "RolePermissionsPage");

/** Super admin only (the server returns the "permissions" section to super admins). */
export const permissionRoutes: RouteObject[] = [
  { element: <RequireSection section="permissions" />, children: [{ path: "/permissions", element: page(<RolePermissionsPage />) }] },
];
