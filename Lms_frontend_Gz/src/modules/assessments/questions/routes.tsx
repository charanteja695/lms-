import type { RouteObject } from "react-router-dom";

import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";
import { RequireRole } from "@/modules/user-management/auth/guards/RequireRole";

const QuestionsListPage = lazyNamed(() => import("./pages/QuestionsListPage"), "QuestionsListPage");
const QuestionCreatePage = lazyNamed(() => import("./pages/QuestionCreatePage"), "QuestionCreatePage");
const QuestionEditPage = lazyNamed(() => import("./pages/QuestionEditPage"), "QuestionEditPage");
const QuestionDetailPage = lazyNamed(() => import("./pages/QuestionDetailPage"), "QuestionDetailPage");
const QuestionImportPage = lazyNamed(() => import("./pages/QuestionImportPage"), "QuestionImportPage");

export const questionRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={["super_admin", "admin", "staff"]} />,
    children: [
      {
        path: "/questions",
        element: page(<WithOverlay><QuestionsListPage /></WithOverlay>),
        children: [{ path: "new", element: drawerPage(<QuestionCreatePage />, "xl") }],
      },
      { path: "/questions/import", element: page(<QuestionImportPage />) },
      {
        path: "/questions/:questionId",
        element: page(<WithOverlay><QuestionDetailPage /></WithOverlay>),
        children: [{ path: "edit", element: drawerPage(<QuestionEditPage />, "xl") }],
      },
    ],
  },
];
