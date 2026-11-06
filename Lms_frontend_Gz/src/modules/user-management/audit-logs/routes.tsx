import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const AuditLogPage = lazyNamed(() => import("./pages/AuditLogPage"), "AuditLogPage");

export const auditLogRoutes: RouteObject[] = [
  {
    element: <RequireSection section="audit_logs" />,
    children: [{ path: "/audit-logs", element: page(<AuditLogPage />) }],
  },
];
