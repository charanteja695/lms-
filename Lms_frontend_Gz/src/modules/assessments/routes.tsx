import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { attemptRoutes } from "@/modules/assessments/attempts/routes";
import { questionRoutes } from "@/modules/assessments/questions/routes";
import { testRoutes } from "@/modules/assessments/tests/routes";

/**
 * Everything here is gated by the single "assessments" section. Question bank, Tests, Attempts
 * and Grading queue are narrower than the section (authors/reviewers/exam managers only, and a
 * student gets a hard 403 reading a question or test definition — not just an empty list, unlike
 * most other modules) — so, same as code-execution's Review/Languages, they are not nav items;
 * MyTestsPage surfaces them as header actions only for a viewer who actually has the scope.
 */
export const assessmentsModuleRoutes: RouteObject[] = [
  { element: <RequireSection section="assessments" />, children: [...attemptRoutes, ...questionRoutes, ...testRoutes] },
];
