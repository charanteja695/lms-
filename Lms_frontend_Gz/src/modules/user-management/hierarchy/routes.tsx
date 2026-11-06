import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const HierarchyPage = lazyNamed(() => import("./pages/HierarchyPage"), "HierarchyPage");

export const hierarchyRoutes: RouteObject[] = [
  { element: <RequireSection section="hierarchy" />, children: [{ path: "/organisation", element: page(<HierarchyPage />) }] },
];
