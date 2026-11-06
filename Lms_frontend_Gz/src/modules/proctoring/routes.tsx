import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { caseRoutes } from "@/modules/proctoring/cases/routes";
import { monitorRoutes } from "@/modules/proctoring/monitor/routes";
import { sessionRoutes } from "@/modules/proctoring/sessions/routes";
import { lazyNamed, page } from "@/shared/routing/page";

const ProctoringHomePage = lazyNamed(() => import("./common/pages/ProctoringHomePage"), "ProctoringHomePage");

/**
 * Gated by the single "proctoring" section. A student only ever sees their own cases; monitoring,
 * the case review queue and the media audit log are institution staff/head, employer member and
 * exam-manager concerns — narrower than the section, so they are reached from the home page's
 * role-based redirect and each screen's own header actions, not separate nav items (see navigation.ts).
 */
export const proctoringModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="proctoring" />,
    children: [{ path: "/proctoring", element: page(<ProctoringHomePage />) }, ...sessionRoutes, ...monitorRoutes, ...caseRoutes],
  },
];
