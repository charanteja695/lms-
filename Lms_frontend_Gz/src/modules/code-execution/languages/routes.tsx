import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";
import { RequireRole } from "@/modules/user-management/auth/guards/RequireRole";

const LanguagesAdminPage = lazyNamed(() => import("./pages/LanguagesAdminPage"), "LanguagesAdminPage");

export const languageRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={["super_admin"]} />,
    children: [{ path: "/languages", element: page(<LanguagesAdminPage />) }],
  },
];
