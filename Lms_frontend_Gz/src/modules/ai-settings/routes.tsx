import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const UsagePage = lazyNamed(() => import("./usage/pages/UsagePage"), "UsagePage");
const ModelsPage = lazyNamed(() => import("./models/pages/ModelsPage"), "ModelsPage");
const PromptsPage = lazyNamed(() => import("./prompts/pages/PromptsPage"), "PromptsPage");
const PromptDetailPage = lazyNamed(() => import("./prompts/pages/PromptDetailPage"), "PromptDetailPage");
const LogsPage = lazyNamed(() => import("./logs/pages/LogsPage"), "LogsPage");

/** Gated by "ai_gateway": AI managers (ai.manage), and heads/staff with ai.usage.own for their own usage page. */
export const aiSettingsModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="ai_gateway" />,
    children: [
      { path: "/ai", element: page(<UsagePage />) },
      { path: "/ai/models", element: page(<ModelsPage />) },
      { path: "/ai/prompts", element: page(<PromptsPage />) },
      { path: "/ai/prompts/:promptKey", element: page(<PromptDetailPage />) },
      { path: "/ai/logs", element: page(<LogsPage />) },
    ],
  },
];
