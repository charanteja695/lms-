import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const CertificatesListPage = lazyNamed(() => import("./pages/CertificatesListPage"), "CertificatesListPage");
const CertificateDetailPage = lazyNamed(() => import("./pages/CertificateDetailPage"), "CertificateDetailPage");

export const issuedRoutes: RouteObject[] = [
  { path: "/certificates/issued", element: page(<CertificatesListPage />) },
  { path: "/certificates/issued/:certificateId", element: page(<CertificateDetailPage />) },
];
