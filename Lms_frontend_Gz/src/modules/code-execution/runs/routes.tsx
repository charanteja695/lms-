import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const CompilerPage = lazyNamed(() => import("./pages/CompilerPage"), "CompilerPage");

export const runRoutes: RouteObject[] = [{ path: "/compiler", element: page(<CompilerPage />) }];
