import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const InterviewHomePage = lazyNamed(() => import("./common/pages/InterviewHomePage"), "InterviewHomePage");
const PracticePage = lazyNamed(() => import("./student/pages/PracticePage"), "PracticePage");
const InterviewRoomPage = lazyNamed(() => import("./student/pages/InterviewRoomPage"), "InterviewRoomPage");
const InterviewReportPage = lazyNamed(() => import("./student/pages/InterviewReportPage"), "InterviewReportPage");
const PlansListPage = lazyNamed(() => import("./plans/pages/PlansListPage"), "PlansListPage");
const PlanFormPage = lazyNamed(() => import("./plans/pages/PlanFormPage"), "PlanFormPage");
const PlanDetailPage = lazyNamed(() => import("./plans/pages/PlanDetailPage"), "PlanDetailPage");
const ScreeningListPage = lazyNamed(() => import("./screening/pages/ScreeningListPage"), "ScreeningListPage");
const ScreeningDetailPage = lazyNamed(() => import("./screening/pages/ScreeningDetailPage"), "ScreeningDetailPage");
const AppealsPage = lazyNamed(() => import("./screening/pages/AppealsPage"), "AppealsPage");

/** Gated by "ai_interview": students practise and take screenings; employers run screening plans and reviews; careers managers own practice plans. */
export const aiInterviewModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="ai_interview" />,
    children: [
      { path: "/interviews", element: page(<InterviewHomePage />) },
      { path: "/interviews/practice", element: page(<PracticePage />) },
      { path: "/interviews/mine/:interviewId", element: page(<InterviewRoomPage />) },
      { path: "/interviews/mine/:interviewId/report", element: page(<InterviewReportPage />) },
      {
        path: "/interviews/plans",
        element: page(<WithOverlay><PlansListPage /></WithOverlay>),
        children: [{ path: "new", element: drawerPage(<PlanFormPage />) }],
      },
      {
        path: "/interviews/plans/:planId",
        element: page(<WithOverlay><PlanDetailPage /></WithOverlay>),
        children: [{ path: "edit", element: drawerPage(<PlanFormPage />) }],
      },
      { path: "/interviews/screening", element: page(<ScreeningListPage />) },
      { path: "/interviews/screening/:interviewId", element: page(<ScreeningDetailPage />) },
      { path: "/interviews/appeals", element: page(<AppealsPage />) },
    ],
  },
];
