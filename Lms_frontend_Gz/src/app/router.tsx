import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";

import { RouteError } from "@/shared/routing/RouteError";
import { PageLoader } from "@/shared/ui/Spinner";

import { billingModuleRoutes } from "@/modules/billing/routes";
import { analyticsModuleRoutes } from "@/modules/analytics/routes";
import { notificationsModuleRoutes } from "@/modules/notifications/routes";
import { aiInterviewModuleRoutes } from "@/modules/ai-interview/routes";
import { aiSettingsModuleRoutes } from "@/modules/ai-settings/routes";
import { aiTutorModuleRoutes } from "@/modules/ai-tutor/routes";
import { assessmentsModuleRoutes } from "@/modules/assessments/routes";
import { careerModuleRoutes } from "@/modules/career/routes";
import { catalogRoutes } from "@/modules/catalog/routes";
import { mediaRoutes } from "@/modules/media/routes";
import { storeRoutes } from "@/modules/store/routes";
import { certificatesModuleRoutes } from "@/modules/certificates/routes";
import { codeExecutionModuleRoutes } from "@/modules/code-execution/routes";
import { dashboardRoutes } from "@/modules/dashboard/routes";
import { jobPortalModuleRoutes } from "@/modules/job-portal/routes";
import { learningModuleRoutes } from "@/modules/learning/routes";
import { proctoringModuleRoutes } from "@/modules/proctoring/routes";
import { supportModuleRoutes } from "@/modules/support/routes";
import { subscriptionsModuleRoutes } from "@/modules/subscriptions/routes";
import { RequireAuth } from "@/modules/user-management/auth/guards/RequireAuth";
import { userManagementRoutes } from "@/modules/user-management/routes";
import { AuthLayout } from "@/shared/layout/AuthLayout";

const LandingPage = lazy(() => import("@/shared/pages/LandingPage").then((m) => ({ default: m.LandingPage })));
const NotFoundPage = lazy(() => import("@/shared/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));
const AppLayout = lazy(() => import("@/shared/layout/AppLayout").then((m) => ({ default: m.AppLayout })));
const PublicLayout = lazy(() => import("@/shared/layout/PublicLayout").then((m) => ({ default: m.PublicLayout })));

/**
 * The app router only composes module routes. To add a module (catalog, learning, ...),
 * create `modules/<name>/routes.tsx` and spread it into the right group below.
 */
export const router = createBrowserRouter([
  // one friendly error page for every route (and a self-reload when a newer release is out)
  {
    errorElement: <RouteError />,
    children: [
    { path: "/landing", element: <Suspense fallback={<PageLoader />}><LandingPage /></Suspense> },
    { path: "/welcome", element: <Suspense fallback={<PageLoader />}><LandingPage /></Suspense> },
    { element: <AuthLayout />, children: [...userManagementRoutes.public] },
    // Public pages that also work while signed in (no PublicOnly redirect).
    { element: <AuthLayout />, children: [...certificatesModuleRoutes.public] },
    { element: <Suspense fallback={<PageLoader />}><PublicLayout /></Suspense>, children: [...careerModuleRoutes.public] },
    {
      element: <RequireAuth />,
      children: [
        ...userManagementRoutes.setup,
        {
          element: <Suspense fallback={<PageLoader />}><AppLayout /></Suspense>,
          children: [
            ...dashboardRoutes,
            ...userManagementRoutes.app,
            ...catalogRoutes,
            ...mediaRoutes,
            ...storeRoutes,
            ...subscriptionsModuleRoutes,
            ...learningModuleRoutes,
            ...codeExecutionModuleRoutes,
            ...assessmentsModuleRoutes,
            ...proctoringModuleRoutes,
            ...certificatesModuleRoutes.app,
            ...aiTutorModuleRoutes,
            ...aiSettingsModuleRoutes,
            ...supportModuleRoutes,
            ...careerModuleRoutes.app,
            ...jobPortalModuleRoutes,
            ...aiInterviewModuleRoutes,
            ...notificationsModuleRoutes,
            ...analyticsModuleRoutes,
            ...billingModuleRoutes,
            { path: "*", element: <Suspense fallback={<PageLoader />}><NotFoundPage /></Suspense> },
          ],
        },
      ],
    },
    ],
  },
]);
