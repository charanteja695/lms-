import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const VerifyCertificatePage = lazyNamed(() => import("./pages/VerifyCertificatePage"), "VerifyCertificatePage");

/** Public (outside sign-in): matches certificate-service's PUBLIC_VERIFY_BASE_URL `<frontend>/verify/{code}`. */
export const verificationRoutes: RouteObject[] = [{ path: "/verify/:code", element: page(<VerifyCertificatePage />) }];
