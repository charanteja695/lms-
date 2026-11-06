import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const CasesListPage = lazyNamed(() => import("./pages/CasesListPage"), "CasesListPage");
const CaseDetailPage = lazyNamed(() => import("./pages/CaseDetailPage"), "CaseDetailPage");
const MyCasesPage = lazyNamed(() => import("./pages/MyCasesPage"), "MyCasesPage");
const MediaAuditPage = lazyNamed(() => import("./pages/MediaAuditPage"), "MediaAuditPage");

export const caseRoutes: RouteObject[] = [
  { path: "/proctoring/cases", element: page(<CasesListPage />) },
  { path: "/proctoring/cases/:caseId", element: page(<CaseDetailPage />) },
  { path: "/proctoring/my-cases", element: page(<MyCasesPage />) },
  { path: "/proctoring/audit", element: page(<MediaAuditPage />) },
];
