import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const InboxPage = lazyNamed(() => import("./inbox/pages/InboxPage"), "InboxPage");
const PreferencesPage = lazyNamed(() => import("./preferences/pages/PreferencesPage"), "PreferencesPage");
const TemplatesPage = lazyNamed(() => import("./admin/pages/TemplatesPage"), "TemplatesPage");
const DeliveriesPage = lazyNamed(() => import("./admin/pages/DeliveriesPage"), "DeliveriesPage");

/** Gated by "notifications" (every signed-in person). Templates and deliveries are super-admin only; the service enforces it. */
export const notificationsModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="notifications" />,
    children: [
      { path: "/notifications", element: page(<InboxPage />) },
      { path: "/notifications/preferences", element: page(<PreferencesPage />) },
      { path: "/notifications/templates", element: page(<TemplatesPage />) },
      { path: "/notifications/deliveries", element: page(<DeliveriesPage />) },
    ],
  },
];
