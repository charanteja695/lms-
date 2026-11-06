import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";

/** Signed-in area. Sends users with pending set-up steps to those steps first. */
export function RequireAuth() {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (user.must_change_password && location.pathname !== "/account/setup/password") {
    return <Navigate to="/account/setup/password" replace />;
  }
  if (!user.must_change_password && user.mfa_setup_required && location.pathname !== "/account/setup/mfa") {
    return <Navigate to="/account/setup/mfa" replace />;
  }
  return <Outlet />;
}
