import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const InstitutionEditPage = lazyNamed(() => import("./pages/InstitutionEditPage"), "InstitutionEditPage");
const InstitutionDetailPage = lazyNamed(() => import("./pages/InstitutionDetailPage"), "InstitutionDetailPage");
const MyOrganizationPage = lazyNamed(() => import("./pages/MyOrganizationPage"), "MyOrganizationPage");

export const institutionRoutes: RouteObject[] = [
  {
    path: "/institutions/:organizationId",
    element: page(<WithOverlay><InstitutionDetailPage /></WithOverlay>),
    children: [{ element: <RequireSection section="institutions" />, children: [{ path: "edit", element: drawerPage(<InstitutionEditPage />) }] }],
  },
  { path: "/my-organization", element: page(<MyOrganizationPage />) },
];
