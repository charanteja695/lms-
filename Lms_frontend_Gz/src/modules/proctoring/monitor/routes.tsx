import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const MonitorListPage = lazyNamed(() => import("./pages/MonitorListPage"), "MonitorListPage");
const MonitorSessionPage = lazyNamed(() => import("./pages/MonitorSessionPage"), "MonitorSessionPage");

export const monitorRoutes: RouteObject[] = [
  { path: "/proctoring/monitor", element: page(<MonitorListPage />) },
  { path: "/proctoring/monitor/:sessionId", element: page(<MonitorSessionPage />) },
];
