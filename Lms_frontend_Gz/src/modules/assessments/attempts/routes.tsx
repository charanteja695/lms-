import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";
import { RequireRole } from "@/modules/user-management/auth/guards/RequireRole";

const MyTestsPage = lazyNamed(() => import("./pages/MyTestsPage"), "MyTestsPage");
const AttemptInstructionsPage = lazyNamed(() => import("./pages/AttemptInstructionsPage"), "AttemptInstructionsPage");
const AttemptPlayerPage = lazyNamed(() => import("./pages/AttemptPlayerPage"), "AttemptPlayerPage");
const AttemptResultPage = lazyNamed(() => import("./pages/AttemptResultPage"), "AttemptResultPage");
const AttemptsListPage = lazyNamed(() => import("./pages/AttemptsListPage"), "AttemptsListPage");
const AttemptDetailPage = lazyNamed(() => import("./pages/AttemptDetailPage"), "AttemptDetailPage");
const GradingQueuePage = lazyNamed(() => import("./pages/GradingQueuePage"), "GradingQueuePage");

export const attemptRoutes: RouteObject[] = [
  // Student test taking and own results
  { path: "/my-tests", element: page(<MyTestsPage />) },
  { path: "/attempts/:attemptId/instructions", element: page(<AttemptInstructionsPage />) },
  { path: "/attempts/:attemptId/take", element: page(<AttemptPlayerPage />) },
  { path: "/attempts/:attemptId/result", element: page(<AttemptResultPage />) },

  // Admin/Staff/InstHead only: View all attempts and grading queue
  {
    element: <RequireRole roles={["super_admin", "admin", "institution_head", "staff"]} />,
    children: [
      { path: "/attempts", element: page(<AttemptsListPage />) },
      { path: "/attempts/:attemptId", element: page(<AttemptDetailPage />) },
      { path: "/grading/queue", element: page(<GradingQueuePage />) },
    ],
  },
];
