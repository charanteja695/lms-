import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { useLogoutMutation } from "@/modules/user-management/auth/api/authApi";
import { loggedOut } from "@/modules/user-management/auth/store/authSlice";

export function useAuth() {
  const user = useAppSelector((state) => state.auth.user);
  const sessionStatus = useAppSelector((state) => state.auth.sessionStatus);
  const isAuthenticated = useAppSelector((state) => Boolean(state.auth.accessToken && state.auth.user));
  return { user, role: user?.role, sessionStatus, isAuthenticated };
}

/** Ends the session on the server, then clears local state even if the server call fails. */
export function useSignOut() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [logout, { isLoading }] = useLogoutMutation();

  const signOut = useCallback(
    async (allSessions = false) => {
      try {
        await logout(allSessions ? { all_sessions: true } : undefined).unwrap();
      } catch {
        /* the session may already be gone; local sign-out still happens */
      }
      dispatch(loggedOut());
      navigate("/login", { replace: true });
    },
    [dispatch, logout, navigate],
  );
  return { signOut, isSigningOut: isLoading };
}
