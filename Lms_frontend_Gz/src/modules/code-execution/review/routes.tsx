import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const ReviewSubmissionsListPage = lazyNamed(() => import("./pages/ReviewSubmissionsListPage"), "ReviewSubmissionsListPage");
const ReviewSubmissionDetailPage = lazyNamed(() => import("./pages/ReviewSubmissionDetailPage"), "ReviewSubmissionDetailPage");

export const reviewRoutes: RouteObject[] = [
  { path: "/review/submissions", element: page(<ReviewSubmissionsListPage />) },
  { path: "/review/submissions/:submissionId", element: page(<ReviewSubmissionDetailPage />) },
];
