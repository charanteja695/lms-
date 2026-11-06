import type { RouteObject } from "react-router-dom";

import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";
import { RequireRole } from "@/modules/user-management/auth/guards/RequireRole";

const TemplatesListPage = lazyNamed(() => import("./pages/TemplatesListPage"), "TemplatesListPage");
const TemplateDetailPage = lazyNamed(() => import("./pages/TemplateDetailPage"), "TemplateDetailPage");
const TemplateFormPage = lazyNamed(() => import("./pages/TemplateFormPage"), "TemplateFormPage");

export const templateRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={["super_admin", "admin"]} />,
    children: [
      {
        path: "/certificates/templates",
        element: page(<WithOverlay><TemplatesListPage /></WithOverlay>),
        children: [{ path: "new", element: drawerPage(<TemplateFormPage />, "xl") }],
      },
      {
        path: "/certificates/templates/:templateId",
        element: page(<WithOverlay><TemplateDetailPage /></WithOverlay>),
        children: [{ path: "edit", element: drawerPage(<TemplateFormPage />, "xl") }],
      },
    ],
  },
];
