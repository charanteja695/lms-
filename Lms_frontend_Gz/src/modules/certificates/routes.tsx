import type { RouteObject } from "react-router-dom";

import { issuedRoutes } from "@/modules/certificates/issued/routes";
import { templateRoutes } from "@/modules/certificates/templates/routes";
import { verificationRoutes } from "@/modules/certificates/verification/routes";
import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const CertificatesHomePage = lazyNamed(() => import("./common/pages/CertificatesHomePage"), "CertificatesHomePage");

/** `app`: signed in, gated by the "certificates" section. `public`: the QR-code verification page, no sign-in. */
export const certificatesModuleRoutes = {
  app: [
    {
      element: <RequireSection section="certificates" />,
      children: [{ path: "/certificates", element: page(<CertificatesHomePage />) }, ...issuedRoutes, ...templateRoutes],
    },
  ] satisfies RouteObject[],
  public: verificationRoutes,
};
