import type { RouteObject } from "react-router-dom";

import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const BatchesListPage = lazyNamed(() => import("./pages/BatchesListPage"), "BatchesListPage");
const BatchCreatePage = lazyNamed(() => import("./pages/BatchCreatePage"), "BatchCreatePage");
const BatchDetailPage = lazyNamed(() => import("./pages/BatchDetailPage"), "BatchDetailPage");

export const batchRoutes: RouteObject[] = [
  {
    path: "/batches",
    element: page(<WithOverlay><BatchesListPage /></WithOverlay>),
    children: [{ path: "new", element: drawerPage(<BatchCreatePage />) }],
  },
  { path: "/batches/:batchId", element: page(<BatchDetailPage />) },
];
