import type { RouteObject } from "react-router-dom";

import { lazyNamed, page } from "@/shared/routing/page";

const PasswordSetupRequiredPage = lazyNamed(() => import("./pages/PasswordSetupRequiredPage"), "PasswordSetupRequiredPage");
const MfaSetupRequiredPage = lazyNamed(() => import("./pages/MfaSetupRequiredPage"), "MfaSetupRequiredPage");
const ProfilePage = lazyNamed(() => import("./pages/ProfilePage"), "ProfilePage");
const SecurityPage = lazyNamed(() => import("./pages/SecurityPage"), "SecurityPage");

/** Mandatory set-up steps, shown full screen before the app. */
export const accountSetupRoutes: RouteObject[] = [
  { path: "/account/setup/password", element: page(<PasswordSetupRequiredPage />) },
  { path: "/account/setup/mfa", element: page(<MfaSetupRequiredPage />) },
];

export const accountRoutes: RouteObject[] = [
  { path: "/account/profile", element: page(<ProfilePage />) },
  { path: "/account/security", element: page(<SecurityPage />) },
];
