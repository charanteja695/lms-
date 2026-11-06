import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { lazyNamed, page } from "@/shared/routing/page";

const CareerHomePage = lazyNamed(() => import("./common/pages/CareerHomePage"), "CareerHomePage");
const MyProfilePage = lazyNamed(() => import("./profile/pages/MyProfilePage"), "MyProfilePage");
const StudentLookupPage = lazyNamed(() => import("./profile/pages/StudentLookupPage"), "StudentLookupPage");
const StudentProfilePage = lazyNamed(() => import("./profile/pages/StudentProfilePage"), "StudentProfilePage");
const ResumesListPage = lazyNamed(() => import("./resumes/pages/ResumesListPage"), "ResumesListPage");
const ResumeEditorPage = lazyNamed(() => import("./resumes/pages/ResumeEditorPage"), "ResumeEditorPage");
const PublicResumePage = lazyNamed(() => import("./public/pages/PublicResumePage"), "PublicResumePage");

/** `app`: gated by the "career" section. `public`: a shared resume link, no sign-in (rendered in PublicLayout). */
export const careerModuleRoutes = {
  app: [
    {
      element: <RequireSection section="career" />,
      children: [
        { path: "/career", element: page(<CareerHomePage />) },
        { path: "/career/profile", element: page(<MyProfilePage />) },
        { path: "/career/resumes", element: page(<ResumesListPage />) },
        { path: "/career/resumes/:resumeId", element: page(<ResumeEditorPage />) },
        { path: "/career/students", element: page(<StudentLookupPage />) },
        { path: "/career/students/:userId", element: page(<StudentProfilePage />) },
      ],
    },
  ] satisfies RouteObject[],
  public: [{ path: "/resume/:token", element: page(<PublicResumePage />) }] satisfies RouteObject[],
};
