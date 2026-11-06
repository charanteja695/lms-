import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const AcademicsPage = lazyNamed(() => import("./pages/AcademicsPage"), "AcademicsPage");
const ResultsPage = lazyNamed(() => import("./pages/ResultsPage"), "ResultsPage");

export const academicsRoutes: RouteObject[] = [
  { element: <RequireSection section="academics" />, children: [{ path: "/academics", element: page(<AcademicsPage />) }, { path: "/results", element: page(<ResultsPage />) }] },
];
