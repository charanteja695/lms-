import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const DashboardPage = lazyNamed(() => import("./dashboards/pages/DashboardPage"), "DashboardPage");
const ReportsPage = lazyNamed(() => import("./reports/pages/ReportsPage"), "ReportsPage");
const ReportDetailPage = lazyNamed(() => import("./reports/pages/ReportDetailPage"), "ReportDetailPage");

/** Gated by "analytics": institution staff, employers, and platform admins holding a domain scope or analytics.view. */
export const analyticsModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="analytics" />,
    children: [
      { path: "/analytics", element: page(<DashboardPage />) },
      { path: "/analytics/reports", element: page(<ReportsPage />) },
      { path: "/analytics/reports/:reportId", element: page(<ReportDetailPage />) },
      { path: "/analytics/:dashboard", element: page(<DashboardPage />) },
    ],
  },
];
