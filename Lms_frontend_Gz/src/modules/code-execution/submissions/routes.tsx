import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const SubmissionsListPage = lazyNamed(() => import("./pages/SubmissionsListPage"), "SubmissionsListPage");
const SubmissionDetailPage = lazyNamed(() => import("./pages/SubmissionDetailPage"), "SubmissionDetailPage");

export const submissionRoutes: RouteObject[] = [
  { path: "/submissions", element: page(<SubmissionsListPage />) },
  { path: "/submissions/:submissionId", element: page(<SubmissionDetailPage />) },
];
