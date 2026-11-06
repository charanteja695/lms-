import type { RouteObject } from "react-router-dom";

import { chatRoutes } from "@/modules/ai-tutor/chat/routes";
import { faqRoutes } from "@/modules/ai-tutor/faq/routes";
import { insightsRoutes } from "@/modules/ai-tutor/insights/routes";
import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const TutorHomePage = lazyNamed(() => import("./common/pages/TutorHomePage"), "TutorHomePage");
const EscalationsPage = lazyNamed(() => import("./escalations/pages/EscalationsPage"), "EscalationsPage");

/**
 * Gated by the single "ai_tutor" section, which spans very different jobs (students chat; staff, authors,
 * support and AI managers each manage a slice). One nav item leads to TutorHomePage, which picks the first
 * screen this person can open; the staff screens link to each other through TutorManageActions.
 */
export const aiTutorModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="ai_tutor" />,
    children: [
      { path: "/tutor", element: page(<TutorHomePage />) },
      ...chatRoutes,
      ...faqRoutes,
      ...insightsRoutes,
      { path: "/tutor/escalations", element: page(<EscalationsPage />) },
    ],
  },
];
