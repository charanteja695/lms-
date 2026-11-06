import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const PrecheckPage = lazyNamed(() => import("./pages/PrecheckPage"), "PrecheckPage");

export const sessionRoutes: RouteObject[] = [{ path: "/proctoring/precheck/:testId", element: page(<PrecheckPage />) }];
