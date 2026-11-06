import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { languageRoutes } from "@/modules/code-execution/languages/routes";
import { problemRoutes } from "@/modules/code-execution/problems/routes";
import { reviewRoutes } from "@/modules/code-execution/review/routes";
import { runRoutes } from "@/modules/code-execution/runs/routes";
import { submissionRoutes } from "@/modules/code-execution/submissions/routes";

/**
 * All gated by the single "code_execution" section. Review (`content.review`/`content.author`/
 * `exams.manage`) and Languages (`super_admin`) are narrower than the section itself, so they
 * are not in the module's nav — reached instead from the Problems page's own actions, which
 * hide them from anyone who would just get a 403.
 */
export const codeExecutionModuleRoutes: RouteObject[] = [
  { element: <RequireSection section="code_execution" />, children: [...runRoutes, ...problemRoutes, ...submissionRoutes, ...reviewRoutes, ...languageRoutes] },
];
