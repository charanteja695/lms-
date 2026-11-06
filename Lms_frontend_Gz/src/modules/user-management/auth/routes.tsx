import type { RouteObject } from "react-router-dom";

import { PublicOnly } from "@/modules/user-management/auth/guards/PublicOnly";
import { lazyNamed, page } from "@/shared/routing/page";

const LoginPage = lazyNamed(() => import("./pages/LoginPage"), "LoginPage");
const SignupPage = lazyNamed(() => import("./pages/SignupPage"), "SignupPage");
const ForgotPasswordPage = lazyNamed(() => import("./pages/ForgotPasswordPage"), "ForgotPasswordPage");
const TokenPasswordPage = lazyNamed(() => import("./pages/TokenPasswordPage"), "TokenPasswordPage");

/** Screens inside the auth layout (no sign-in needed). */
export const authRoutes: RouteObject[] = [
  {
    element: <PublicOnly />,
    children: [
      { path: "/login", element: page(<LoginPage />) },
      { path: "/forgot-password", element: page(<ForgotPasswordPage />) },
      { path: "/register", element: page(<SignupPage />) },
    ],
  },
  // Emailed links work whether or not someone is signed in on this device.
  { path: "/reset-password", element: page(<TokenPasswordPage mode="reset" />) },
  { path: "/set-password", element: page(<TokenPasswordPage mode="setup" />) },
];
