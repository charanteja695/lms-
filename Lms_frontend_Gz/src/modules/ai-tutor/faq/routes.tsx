import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const FaqPage = lazyNamed(() => import("./pages/FaqPage"), "FaqPage");
const FaqManagePage = lazyNamed(() => import("./pages/FaqManagePage"), "FaqManagePage");

export const faqRoutes: RouteObject[] = [
  { path: "/tutor/faq", element: page(<FaqPage />) },
  { path: "/tutor/faqs", element: page(<FaqManagePage />) },
];
