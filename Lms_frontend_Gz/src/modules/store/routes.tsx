import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const StorePage = lazyNamed(() => import("./pages/StorePage"), "StorePage");

/** Self-registered learners only (the server gives them the "store" section). */
export const storeRoutes: RouteObject[] = [{ element: <RequireSection section="store" />, children: [{ path: "/store", element: page(<StorePage />) }] }];
