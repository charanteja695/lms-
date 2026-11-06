import type { RouteObject } from "react-router-dom";

import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const CourseRequestsListPage = lazyNamed(() => import("./pages/CourseRequestsListPage"), "CourseRequestsListPage");
const CourseRequestCreatePage = lazyNamed(() => import("./pages/CourseRequestCreatePage"), "CourseRequestCreatePage");
const CourseRequestDetailPage = lazyNamed(() => import("./pages/CourseRequestDetailPage"), "CourseRequestDetailPage");

export const courseRequestRoutes: RouteObject[] = [
  {
    path: "/course-requests",
    element: page(<WithOverlay><CourseRequestsListPage /></WithOverlay>),
    children: [{ path: "new", element: drawerPage(<CourseRequestCreatePage />) }],
  },
  { path: "/course-requests/:courseRequestId", element: page(<CourseRequestDetailPage />) },
];
