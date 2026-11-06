import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const EmployersListPage = lazyNamed(() => import("./pages/EmployersListPage"), "EmployersListPage");
const EmployerCreatePage = lazyNamed(() => import("./pages/EmployerCreatePage"), "EmployerCreatePage");
const EmployerEditPage = lazyNamed(() => import("./pages/EmployerEditPage"), "EmployerEditPage");
const EmployerDetailPage = lazyNamed(() => import("./pages/EmployerDetailPage"), "EmployerDetailPage");

export const employerRoutes: RouteObject[] = [
  {
    element: <RequireSection section="employers" />,
    children: [
      {
        path: "/employers",
        element: page(<WithOverlay><EmployersListPage /></WithOverlay>),
        children: [{ path: "new", element: drawerPage(<EmployerCreatePage />) }],
      },
    ],
  },
  {
    path: "/employers/:organizationId",
    element: page(<WithOverlay><EmployerDetailPage /></WithOverlay>),
    children: [{ element: <RequireSection section="employers" />, children: [{ path: "edit", element: drawerPage(<EmployerEditPage />) }] }],
  },
];
