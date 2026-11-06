import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { batchRoutes } from "@/modules/learning/batches/routes";
import { enrollmentRoutes } from "@/modules/learning/enrollments/routes";

/** Batches and enrolments/course player, both gated by the single "learning" section. */
export const learningModuleRoutes: RouteObject[] = [
  { element: <RequireSection section="learning" />, children: [...batchRoutes, ...enrollmentRoutes] },
];
