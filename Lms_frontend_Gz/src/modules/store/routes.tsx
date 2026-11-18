import type { RouteObject } from "react-router-dom";

import { RequireAuth } from "@/modules/user-management/auth/guards/RequireAuth";
import { RequireRole } from "@/modules/user-management/auth/guards/RequireRole";
import { RequireIndependentStudent } from "@/modules/store/guards/RequireIndependentStudent";
import { lazyNamed, page } from "@/shared/routing/page";

const BrowseCoursesPage = lazyNamed(() => import("./pages/BrowseCoursesPage"), "BrowseCoursesPage");
const CoursePlansPage = lazyNamed(() => import("./pages/CoursePlansPage"), "CoursePlansPage");
const CheckoutPage = lazyNamed(() => import("./pages/CheckoutPage"), "CheckoutPage");
const PaymentStatusPage = lazyNamed(() => import("./pages/PaymentStatusPage"), "PaymentStatusPage");
const MySubscriptionPage = lazyNamed(() => import("./pages/MySubscriptionPage"), "MySubscriptionPage");
const MyPaymentRequestsPage = lazyNamed(() => import("./pages/MyPaymentRequestsPage"), "MyPaymentRequestsPage");
const PaymentHistoryPage = lazyNamed(() => import("./pages/PaymentHistoryPage"), "PaymentHistoryPage");
const InstitutionPaymentsPage = lazyNamed(() => import("./pages/InstitutionPaymentsPage"), "InstitutionPaymentsPage");
const InstitutionalPurchaseRequestPage = lazyNamed(
  () => import("@/modules/billing/institutional/pages/InstitutionalPurchaseRequestPage"),
  "InstitutionalPurchaseRequestPage"
);
const InstitutionQuotationReviewPage = lazyNamed(
  () => import("@/modules/billing/institutional/pages/InstitutionQuotationReviewPage"),
  "InstitutionQuotationReviewPage"
);
const InstitutionalPurchasesPage = lazyNamed(
  () => import("@/modules/billing/institutional/pages/InstitutionalPurchasesPage"),
  "InstitutionalPurchasesPage"
);
const AdminInstitutionalRequestsPage = lazyNamed(
  () => import("@/modules/billing/institutional/pages/AdminInstitutionalRequestsPage"),
  "AdminInstitutionalRequestsPage"
);
const AdminCoursePricingPage = lazyNamed(
  () => import("@/modules/billing/institutional/pages/AdminCoursePricingPage"),
  "AdminCoursePricingPage"
);

/** Student subscription plans, course browse, checkout, requests, status, payment history & Institution Head payments. */
export const storeRoutes: RouteObject[] = [
  {
    element: <RequireAuth />,
    children: [
      { path: "/store", element: page(<BrowseCoursesPage />) },
      { path: "/browse-courses", element: page(<BrowseCoursesPage />) },
      { path: "/courses/:courseId/plans", element: page(<CoursePlansPage />) },
      { path: "/courses/:courseId/details", element: page(<CoursePlansPage />) },
      {
        element: <RequireIndependentStudent />,
        children: [
          { path: "/checkout", element: page(<CheckoutPage />) },
          { path: "/payment-status/:txId", element: page(<PaymentStatusPage />) },
          { path: "/my-subscription", element: page(<MySubscriptionPage />) },
          { path: "/my-payment-requests", element: page(<MyPaymentRequestsPage />) },
          { path: "/payment-history", element: page(<PaymentHistoryPage />) },
        ],
      },
      {
        element: <RequireRole roles={["institution_head", "super_admin"]} />,
        children: [
          { path: "/institution-payments", element: page(<InstitutionPaymentsPage />) },
          { path: "/institution/course-requests/new", element: page(<InstitutionalPurchaseRequestPage />) },
          { path: "/institution/course-requests/:requestId", element: page(<InstitutionQuotationReviewPage />) },
          { path: "/institution/purchases", element: page(<InstitutionalPurchasesPage />) },
          { path: "/admin/institutional-requests", element: page(<AdminInstitutionalRequestsPage />) },
          { path: "/admin/course-pricing", element: page(<AdminCoursePricingPage />) },
        ],
      },
    ],
  },
];
