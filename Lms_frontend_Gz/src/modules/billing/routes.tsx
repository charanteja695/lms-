import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const BillingHomePage = lazyNamed(() => import("./common/pages/BillingHomePage"), "BillingHomePage");
const SubscriptionPlansAdminPage = lazyNamed(
  () => import("./subscription-plans/pages/SubscriptionPlansAdminPage"),
  "SubscriptionPlansAdminPage",
);
const TransactionsAdminPage = lazyNamed(
  () => import("./subscription-plans/pages/TransactionsAdminPage"),
  "TransactionsAdminPage",
);
const PaymentReportsPage = lazyNamed(
  () => import("./subscription-plans/pages/PaymentReportsPage"),
  "PaymentReportsPage",
);
const InvoicesPage = lazyNamed(() => import("./invoices/pages/InvoicesPage"), "InvoicesPage");
const InvoiceDetailPage = lazyNamed(() => import("./invoices/pages/InvoiceDetailPage"), "InvoiceDetailPage");
const QuotesPage = lazyNamed(() => import("./quotes/pages/QuotesPage"), "QuotesPage");
const QuoteCreatePage = lazyNamed(() => import("./quotes/pages/QuoteCreatePage"), "QuoteCreatePage");
const QuoteDetailPage = lazyNamed(() => import("./quotes/pages/QuoteDetailPage"), "QuoteDetailPage");
const PlansPage = lazyNamed(() => import("./plans/pages/PlansPage"), "PlansPage");
const PricesPage = lazyNamed(() => import("./prices/pages/PricesPage"), "PricesPage");
const MyProfilePage = lazyNamed(() => import("./profile/pages/MyProfilePage"), "MyProfilePage");
const OrgProfilePage = lazyNamed(() => import("./profile/pages/OrgProfilePage"), "OrgProfilePage");
const InstitutionalPurchaseRequestPage = lazyNamed(
  () => import("./institutional/pages/InstitutionalPurchaseRequestPage"),
  "InstitutionalPurchaseRequestPage"
);
const InstitutionQuotationReviewPage = lazyNamed(
  () => import("./institutional/pages/InstitutionQuotationReviewPage"),
  "InstitutionQuotationReviewPage"
);
const InstitutionalPurchasesPage = lazyNamed(
  () => import("./institutional/pages/InstitutionalPurchasesPage"),
  "InstitutionalPurchasesPage"
);
const AdminInstitutionalRequestsPage = lazyNamed(
  () => import("./institutional/pages/AdminInstitutionalRequestsPage"),
  "AdminInstitutionalRequestsPage"
);
const AdminCoursePricingPage = lazyNamed(
  () => import("./institutional/pages/AdminCoursePricingPage"),
  "AdminCoursePricingPage"
);
const PriceHistoryPage = lazyNamed(
  () => import("./institutional/pages/PriceHistoryPage"),
  "PriceHistoryPage"
);
const InstitutionalPaymentPage = lazyNamed(
  () => import("./institutional/pages/InstitutionalPaymentPage"),
  "InstitutionalPaymentPage"
);
const InstitutionalCourseManagementPage = lazyNamed(
  () => import("./institutional/pages/InstitutionalCourseManagementPage"),
  "InstitutionalCourseManagementPage"
);

/** Gated by "billing" or "subscriptions": institution heads, employer admins, and billing managers. The service decides each action. */
export const billingModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section={["billing", "subscriptions"]} />,
    children: [
      { path: "/institution/course-management", element: page(<InstitutionalCourseManagementPage />) },
      { path: "/institution/management", element: page(<InstitutionalCourseManagementPage />) },
      { path: "/billing", element: page(<BillingHomePage />) },
      { path: "/billing/subscription-plans", element: page(<SubscriptionPlansAdminPage />) },
      { path: "/billing/transactions", element: page(<TransactionsAdminPage />) },
      { path: "/billing/reports", element: page(<PaymentReportsPage />) },
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
      { path: "/institution/course-requests/new", element: page(<InstitutionalPurchaseRequestPage />) },
      { path: "/institution/course-requests/:requestId", element: page(<InstitutionQuotationReviewPage />) },
      { path: "/institution/course-requests/:requestId/payment", element: page(<InstitutionalPaymentPage />) },
      { path: "/institution/purchases", element: page(<InstitutionalPurchasesPage />) },
      { path: "/admin/institutional-requests", element: page(<AdminInstitutionalRequestsPage />) },
      { path: "/admin/course-pricing", element: page(<AdminCoursePricingPage />) },
      { path: "/admin/course-pricing/history", element: page(<PriceHistoryPage />) },
      { path: "/admin/price-history", element: page(<PriceHistoryPage />) },
    ],
  },
];
