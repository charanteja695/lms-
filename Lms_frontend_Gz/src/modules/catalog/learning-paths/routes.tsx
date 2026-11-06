import type { RouteObject } from "react-router-dom";

import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const LearningPathsListPage = lazyNamed(() => import("./pages/LearningPathsListPage"), "LearningPathsListPage");
const LearningPathCreatePage = lazyNamed(() => import("./pages/LearningPathCreatePage"), "LearningPathCreatePage");
const LearningPathEditPage = lazyNamed(() => import("./pages/LearningPathEditPage"), "LearningPathEditPage");
const LearningPathDetailPage = lazyNamed(() => import("./pages/LearningPathDetailPage"), "LearningPathDetailPage");

export const learningPathRoutes: RouteObject[] = [
  {
    path: "/learning-paths",
    element: page(<WithOverlay><LearningPathsListPage /></WithOverlay>),
    children: [{ path: "new", element: drawerPage(<LearningPathCreatePage />) }],
  },
  {
    path: "/learning-paths/:learningPathId",
    element: page(<WithOverlay><LearningPathDetailPage /></WithOverlay>),
    children: [{ path: "edit", element: drawerPage(<LearningPathEditPage />) }],
  },
];
