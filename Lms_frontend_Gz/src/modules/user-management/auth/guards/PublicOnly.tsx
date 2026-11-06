import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";

/** Login, sign-up, forgot password: signed-in users go to the app instead (to the page they were sent from, if any). */
export function PublicOnly() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  return isAuthenticated ? <Navigate to={from ?? "/"} replace /> : <Outlet />;
}
