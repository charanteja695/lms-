import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { RequireJobRole } from "@/modules/job-portal/common/guards/RequireJobRole";
import { drawerPage, WithOverlay } from "@/shared/routing/drawerRoute";
import { lazyNamed, page } from "@/shared/routing/page";

const Home = lazyNamed(() => import("./common/pages/JobPortalHomePage"), "JobPortalHomePage");
const JobBoardPage = lazyNamed(() => import("./board/pages/JobBoardPage"), "JobBoardPage");
const JobDetailPage = lazyNamed(() => import("./board/pages/JobDetailPage"), "JobDetailPage");
const ApplyJobPage = lazyNamed(() => import("./board/pages/ApplyJobPage"), "ApplyJobPage");
const MyApplicationsPage = lazyNamed(() => import("./applications/pages/MyApplicationsPage"), "MyApplicationsPage");
const MyApplicationPage = lazyNamed(() => import("./applications/pages/MyApplicationPage"), "MyApplicationPage");
const EmployerJobsPage = lazyNamed(() => import("./employer/pages/EmployerJobsPage"), "EmployerJobsPage");
const JobFormPage = lazyNamed(() => import("./employer/pages/JobFormPage"), "JobFormPage");
const EmployerJobPage = lazyNamed(() => import("./employer/pages/EmployerJobPage"), "EmployerJobPage");
const ApplicantPage = lazyNamed(() => import("./employer/pages/ApplicantPage"), "ApplicantPage");
const CompanyProfilePage = lazyNamed(() => import("./employer/pages/CompanyProfilePage"), "CompanyProfilePage");
const DrivesPage = lazyNamed(() => import("./drives/pages/DrivesPage"), "DrivesPage");
const DrivePage = lazyNamed(() => import("./drives/pages/DrivePage"), "DrivePage");
const InstitutionPlacementsPage = lazyNamed(() => import("./institution/pages/InstitutionPlacementsPage"), "InstitutionPlacementsPage");
const JobAdminPage = lazyNamed(() => import("./admin/pages/JobAdminPage"), "JobAdminPage");

/**
 * Gated by the "job_portal" section and enforced with strict RBAC guards:
 * - /jobs: Root landing page routes to role-specific dashboard
 * - Student routes: /jobs/board, /jobs/applications (inaccessible by admins)
 * - Admin & Employer routes: /jobs/employer, /jobs/company (inaccessible by students)
 * - Institution routes: /jobs/institution (staff, heads, admins)
 * - Drives: /jobs/drives
 */
export const jobPortalModuleRoutes: RouteObject[] = [
  {
    element: <RequireSection section="job_portal" />,
    children: [
      { path: "/jobs", element: page(<Home />) },

      // Student-only routes (Admins attempting direct access are redirected to /jobs/employer)
      {
        element: <RequireJobRole allowedRoles={["student"]} />,
        children: [
          { path: "/jobs/board", element: page(<JobBoardPage />) },
          { path: "/jobs/board/:jobId", element: page(<JobDetailPage />) },
          { path: "/jobs/board/:jobId/apply", element: page(<ApplyJobPage />) },
          { path: "/jobs/applications", element: page(<MyApplicationsPage />) },
          { path: "/jobs/applications/:applicationId", element: page(<MyApplicationPage />) },
        ],
      },

      // Admin & Employer routes (Students attempting direct access are redirected to /jobs/board)
      {
        element: <RequireJobRole allowedRoles={["super_admin", "admin", "employer_admin", "recruiter"]} />,
        children: [
          { path: "/jobs/company", element: page(<CompanyProfilePage />) },
          { path: "/jobs/new", element: page(<JobFormPage />) },
          { path: "/jobs/:jobId/edit", element: page(<JobFormPage />) },
          {
            path: "/jobs/employer",
            element: page(<WithOverlay><EmployerJobsPage /></WithOverlay>),
            children: [{ path: "new", element: drawerPage(<JobFormPage />, "xl") }],
          },
          {
            path: "/jobs/employer/:jobId",
            element: page(<WithOverlay><EmployerJobPage /></WithOverlay>),
            children: [{ path: "edit", element: drawerPage(<JobFormPage />, "xl") }],
          },
          { path: "/jobs/employer/applications/:applicationId", element: page(<ApplicantPage />) },
        ],
      },

      // Institution placement management (Institution heads, staff, admins)
      {
        element: <RequireJobRole allowedRoles={["institution_head", "staff", "super_admin", "admin"]} />,
        children: [
          { path: "/jobs/institution", element: page(<InstitutionPlacementsPage />) },
        ],
      },

      // Placement drives (Heads, staff, employers, admins)
      {
        element: <RequireJobRole allowedRoles={["institution_head", "staff", "super_admin", "admin", "employer_admin", "recruiter"]} />,
        children: [
          { path: "/jobs/drives", element: page(<DrivesPage />) },
          { path: "/jobs/drives/:driveId", element: page(<DrivePage />) },
        ],
      },

      // Platform Job approvals (Super Admin & Admin)
      {
        element: <RequireJobRole allowedRoles={["super_admin", "admin"]} />,
        children: [
          { path: "/jobs/admin", element: page(<JobAdminPage />) },
        ],
      },
    ],
  },
];
