import { hierarchyRoutes } from "@/modules/user-management/hierarchy/routes";
import { academicsRoutes } from "@/modules/user-management/academics/routes";
import { accountRoutes, accountSetupRoutes } from "@/modules/user-management/account/routes";
import { adminRoutes } from "@/modules/user-management/admins/routes";
import { auditLogRoutes } from "@/modules/user-management/audit-logs/routes";
import { authRoutes } from "@/modules/user-management/auth/routes";
import { downloadRoutes } from "@/modules/user-management/downloads/routes";
import { employerRoutes } from "@/modules/user-management/employers/routes";
import { institutionRoutes } from "@/modules/user-management/institutions/routes";
import { manageRoutes } from "@/modules/user-management/manage/routes";
import { permissionRoutes } from "@/modules/user-management/permissions/routes";
import { userRoutes } from "@/modules/user-management/users/routes";

/** User management screens, grouped by where they render. */
export const userManagementRoutes = {
  /** Inside the auth layout; no sign-in needed. */
  public: authRoutes,
  /** Signed in, full screen (mandatory set-up steps). */
  setup: accountSetupRoutes,
  /** Signed in, inside the app layout. */
  app: [...manageRoutes, ...accountRoutes, ...adminRoutes, ...institutionRoutes, ...employerRoutes, ...userRoutes, ...downloadRoutes, ...auditLogRoutes, ...permissionRoutes, ...academicsRoutes, ...hierarchyRoutes],
};
