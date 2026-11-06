import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const DashboardPage = lazyNamed(() => import("./pages/DashboardPage"), "DashboardPage");

export const dashboardRoutes: RouteObject[] = [{ path: "/", element: page(<DashboardPage />) }];
