import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const CourseInsightsPage = lazyNamed(() => import("./pages/CourseInsightsPage"), "CourseInsightsPage");
const EvalSetPage = lazyNamed(() => import("./pages/EvalSetPage"), "EvalSetPage");

export const insightsRoutes: RouteObject[] = [
  { path: "/tutor/insights", element: page(<CourseInsightsPage />) },
  { path: "/tutor/eval-sets/:evalSetId", element: page(<EvalSetPage />) },
];
