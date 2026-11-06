import type { RouteObject } from "react-router-dom";

import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";
import { RequireRole } from "@/modules/user-management/auth/guards/RequireRole";

const TestsListPage = lazyNamed(() => import("./pages/TestsListPage"), "TestsListPage");
const TestCreatePage = lazyNamed(() => import("./pages/TestCreatePage"), "TestCreatePage");
const TestEditPage = lazyNamed(() => import("./pages/TestEditPage"), "TestEditPage");
const TestDetailPage = lazyNamed(() => import("./pages/TestDetailPage"), "TestDetailPage");

export const testRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={["super_admin", "admin", "institution_head", "staff"]} />,
    children: [
      {
        path: "/tests",
        element: page(<WithOverlay><TestsListPage /></WithOverlay>),
        children: [{ path: "new", element: drawerPage(<TestCreatePage />, "xl") }],
      },
      {
        path: "/tests/:testId",
        element: page(<WithOverlay><TestDetailPage /></WithOverlay>),
        children: [{ path: "edit", element: drawerPage(<TestEditPage />, "xl") }],
      },
    ],
  },
];
