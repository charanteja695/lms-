import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const UsersListPage = lazyNamed(() => import("./pages/UsersListPage"), "UsersListPage");
const UserDetailPage = lazyNamed(() => import("./pages/UserDetailPage"), "UserDetailPage");
const UserCreatePage = lazyNamed(() => import("./pages/UserCreatePage"), "UserCreatePage");
const UserEditPage = lazyNamed(() => import("./pages/UserEditPage"), "UserEditPage");
const UserImportPage = lazyNamed(() => import("./pages/UserImportPage"), "UserImportPage");

export const userRoutes: RouteObject[] = [
  {
    element: <RequireSection section="users" />,
    children: [
      {
        path: "/users",
        element: page(<WithOverlay><UsersListPage resource="users" /></WithOverlay>),
        children: [{ path: "new", element: drawerPage(<UserCreatePage resource="users" />) }],
      },
      { path: "/users/import", element: page(<UserImportPage />) },
      {
        path: "/users/:userId",
        element: page(<WithOverlay><UserDetailPage resource="users" /></WithOverlay>),
        children: [{ path: "edit", element: drawerPage(<UserEditPage resource="users" />) }],
      },
    ],
  },
];
