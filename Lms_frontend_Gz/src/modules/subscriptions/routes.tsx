import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { courseRequestRoutes } from "@/modules/subscriptions/course-requests/routes";
import { subscriptionRoutes } from "@/modules/subscriptions/subscriptions/routes";

/** Course requests and subscriptions, both gated by the single "subscriptions" section. */
export const subscriptionsModuleRoutes: RouteObject[] = [
  { element: <RequireSection section="subscriptions" />, children: [...courseRequestRoutes, ...subscriptionRoutes] },
];
