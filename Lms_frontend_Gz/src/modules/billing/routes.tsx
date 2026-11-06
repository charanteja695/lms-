import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const BillingHomePage = lazyNamed(() => import("./common/pages/BillingHomePage"), "BillingHomePage");
const InvoicesPage = lazyNamed(() => import("./invoices/pages/InvoicesPage"), "InvoicesPage");
const InvoiceDetailPage = lazyNamed(() => import("./invoices/pages/InvoiceDetailPage"), "InvoiceDetailPage");
const QuotesPage = lazyNamed(() => import("./quotes/pages/QuotesPage"), "QuotesPage");
const QuoteCreatePage = lazyNamed(() => import("./quotes/pages/QuoteCreatePage"), "QuoteCreatePage");
const QuoteDetailPage = lazyNamed(() => import("./quotes/pages/QuoteDetailPage"), "QuoteDetailPage");
const PlansPage = lazyNamed(() => import("./plans/pages/PlansPage"), "PlansPage");
const PricesPage = lazyNamed(() => import("./prices/pages/PricesPage"), "PricesPage");
const MyProfilePage = lazyNamed(() => import("./profile/pages/MyProfilePage"), "MyProfilePage");
const OrgProfilePage = lazyNamed(() => import("./profile/pages/OrgProfilePage"), "OrgProfilePage");

/** Gated by "billing": institution heads, employer admins, and billing managers. The service decides each action. */
export const billingModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="billing" />,
    children: [
      { path: "/billing", element: page(<BillingHomePage />) },
      { path: "/billing/invoices", element: page(<InvoicesPage />) },
      { path: "/billing/invoices/:invoiceId", element: page(<InvoiceDetailPage />) },
      {
        path: "/billing/quotes",
        element: page(<WithOverlay><QuotesPage /></WithOverlay>),
        children: [{ path: "new", element: drawerPage(<QuoteCreatePage />) }],
      },
      { path: "/billing/quotes/:quoteId", element: page(<QuoteDetailPage />) },
      { path: "/billing/plans", element: page(<PlansPage />) },
      { path: "/billing/prices", element: page(<PricesPage />) },
      { path: "/billing/profile", element: page(<MyProfilePage />) },
      { path: "/billing/organizations/:orgId/profile", element: page(<OrgProfilePage />) },
    ],
  },
];
