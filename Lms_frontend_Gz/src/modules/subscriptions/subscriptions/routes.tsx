import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const SubscriptionsListPage = lazyNamed(() => import("./pages/SubscriptionsListPage"), "SubscriptionsListPage");
const SubscriptionDetailPage = lazyNamed(() => import("./pages/SubscriptionDetailPage"), "SubscriptionDetailPage");

export const subscriptionRoutes: RouteObject[] = [
  { path: "/subscriptions", element: page(<SubscriptionsListPage />) },
  { path: "/subscriptions/:subscriptionId", element: page(<SubscriptionDetailPage />) },
];
