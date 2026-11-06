import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const JobsPage = lazyNamed(() => import("./pages/JobsPage"), "JobsPage");

export const downloadRoutes: RouteObject[] = [
  {
    element: <RequireSection section="downloads" />,
    children: [
      { path: "/downloads", element: page(<JobsPage />) },
      { path: "/downloads/:jobId", element: page(<JobsPage />) },
    ],
  },
];
