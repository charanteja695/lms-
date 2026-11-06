import type { RouteObject } from "react-router-dom";

import { RequireSection } from "@/modules/user-management/auth/guards/RequireSection";
import { RequirePeopleRole } from "@/modules/user-management/manage/people/RequirePeopleRole";
import { lazyNamed, page } from "@/shared/routing/page";

const PeoplePage = lazyNamed(() => import("./people/pages/PeoplePage"), "PeoplePage");
const InstitutionsPage = lazyNamed(() => import("./institutions/pages/InstitutionsPage"), "InstitutionsPage");

/** User management: Admins, Institutions, Institution heads, Staff and Students. Forms open as pop-ups on each page. */
export const manageRoutes: RouteObject[] = [
  { element: <RequireSection section="admins" />, children: [{ path: "/admins", element: page(<PeoplePage kind="admin" />) }] },
  { element: <RequireSection section="institutions" />, children: [{ path: "/institutions", element: page(<InstitutionsPage />) }] },
  { element: <RequirePeopleRole role="institution_head" />, children: [{ path: "/institution-heads", element: page(<PeoplePage key="heads" kind="institution_head" />) }] },
  { element: <RequirePeopleRole role="staff" />, children: [{ path: "/staff", element: page(<PeoplePage key="staff" kind="staff" />) }] },
  { element: <RequirePeopleRole role="student" />, children: [{ path: "/students", element: page(<PeoplePage key="students" kind="student" />) }] },
];
