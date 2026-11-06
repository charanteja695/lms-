import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

// Admins are users served under /admins. The list (with its add/edit pop-up) is in manage/routes.tsx; this is one admin's page.
const UserDetailPage = lazyNamed(() => import("../users/pages/UserDetailPage"), "UserDetailPage");
const UserEditPage = lazyNamed(() => import("../users/pages/UserEditPage"), "UserEditPage");

export const adminRoutes: RouteObject[] = [
  {
    element: <RequireSection section="admins" />,
    children: [
      {
        path: "/admins/:userId",
        element: page(<WithOverlay><UserDetailPage resource="admins" /></WithOverlay>),
        children: [{ path: "edit", element: drawerPage(<UserEditPage resource="admins" />) }],
      },
    ],
  },
];
