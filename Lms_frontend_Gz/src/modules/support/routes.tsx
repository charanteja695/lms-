import type { RouteObject } from "react-router-dom";

import { myTicketRoutes } from "@/modules/support/tickets/routes";
import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const SupportHomePage = lazyNamed(() => import("./common/pages/SupportHomePage"), "SupportHomePage");
const QueuePage = lazyNamed(() => import("./agent/pages/QueuePage"), "QueuePage");
const AgentTicketPage = lazyNamed(() => import("./agent/pages/AgentTicketPage"), "AgentTicketPage");
const SlaReportPage = lazyNamed(() => import("./reports/pages/SlaReportPage"), "SlaReportPage");
const CannedRepliesPage = lazyNamed(() => import("./config/pages/CannedRepliesPage"), "CannedRepliesPage");
const SlaPoliciesPage = lazyNamed(() => import("./config/pages/SlaPoliciesPage"), "SlaPoliciesPage");

/**
 * Gated by the "support" section: students (their tickets) and agents (institution staff/heads, the exam team,
 * support managers). One nav item leads to SupportHomePage, which picks the side; agent screens link to each
 * other through SupportManageActions.
 */
export const supportModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="support" />,
    children: [
      { path: "/support", element: page(<SupportHomePage />) },
      ...myTicketRoutes,
      { path: "/support/queue", element: page(<QueuePage />) },
      { path: "/support/queue/:ticketId", element: page(<AgentTicketPage />) },
      { path: "/support/reports", element: page(<SlaReportPage />) },
      { path: "/support/canned-replies", element: page(<CannedRepliesPage />) },
      { path: "/support/sla-policies", element: page(<SlaPoliciesPage />) },
    ],
  },
];
