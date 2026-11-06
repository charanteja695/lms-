import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { builderRoutes } from "@/modules/catalog/builder/routes";
import { courseRoutes } from "@/modules/catalog/courses/routes";
import { learningPathRoutes } from "@/modules/catalog/learning-paths/routes";

/** Courses and learning paths, both gated by the single "catalog" section. */
export const catalogRoutes: RouteObject[] = [
  { element: <RequireSection section="catalog" />, children: [...courseRoutes, ...builderRoutes, ...learningPathRoutes] },
];
