import { useEffect, type ReactNode } from "react";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { store } from "@/app/store";
import { refreshSession } from "@/core/api/baseApi";
import { sessionRestoreFinished } from "@/modules/user-management/auth/store/authSlice";
import { PageLoader } from "@/shared/ui";

/** On start-up, exchange the refresh cookie for an access token once. */
export function SessionRestorer({ children }: { children: ReactNode }) {
  const dispatch = useAppDispatch();
  const status = useAppSelector((state) => state.auth.sessionStatus);

  useEffect(() => {
    if (status !== "checking") return;
    void refreshSession({
      getState: store.getState,
      dispatch: store.dispatch,
      signal: new AbortController().signal,
      abort: () => undefined,
      extra: undefined,
      endpoint: "restoreSession",
      type: "mutation",
    }).finally(() => dispatch(sessionRestoreFinished()));
  }, [dispatch, status]);

  return status === "checking" ? <PageLoader label="Restoring your session…" /> : <>{children}</>;
}
