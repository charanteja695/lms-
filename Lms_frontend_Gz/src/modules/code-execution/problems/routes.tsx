import type { RouteObject } from "react-router-dom";

import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";
import { RequireRole } from "@/modules/user-management/auth/guards/RequireRole";

const ProblemsListPage = lazyNamed(() => import("./pages/ProblemsListPage"), "ProblemsListPage");
const ProblemCreatePage = lazyNamed(() => import("./pages/ProblemCreatePage"), "ProblemCreatePage");
const ProblemEditPage = lazyNamed(() => import("./pages/ProblemEditPage"), "ProblemEditPage");
const ProblemDetailPage = lazyNamed(() => import("./pages/ProblemDetailPage"), "ProblemDetailPage");

export const problemRoutes: RouteObject[] = [
  {
    path: "/problems",
    element: page(<WithOverlay><ProblemsListPage /></WithOverlay>),
    children: [
      {
        element: <RequireRole roles={["super_admin", "admin", "staff"]} />,
        children: [{ path: "new", element: drawerPage(<ProblemCreatePage />, "xl") }],
      },
    ],
  },
  {
    path: "/problems/:problemId",
    element: page(<WithOverlay><ProblemDetailPage /></WithOverlay>),
    children: [
      {
        element: <RequireRole roles={["super_admin", "admin", "staff"]} />,
        children: [{ path: "edit", element: drawerPage(<ProblemEditPage />, "xl") }],
      },
    ],
  },
];
