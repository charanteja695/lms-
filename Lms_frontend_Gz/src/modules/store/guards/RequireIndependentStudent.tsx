import { useEffect, useRef } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAppDispatch } from "@/app/hooks";
import { toastAdded } from "@/core/toast/toastSlice";
import { useStudentType } from "@/modules/user-management/auth/hooks/useStudentType";
import { PageLoader } from "@/shared/ui";

export function RequireIndependentStudent({ children }: { children?: React.ReactNode }) {
  const dispatch = useAppDispatch();
  const { isResolving, isInstitutionStudent } = useStudentType();
  const toastFired = useRef(false);

  useEffect(() => {
    if (!isResolving && isInstitutionStudent && !toastFired.current) {
      toastFired.current = true;
      dispatch(
        toastAdded({
          tone: "info",
          title: "Institutional Account",
          description:
            "Institution students receive course access directly through their college package. Individual payments and subscriptions are unavailable.",
        }),
      );
    }
  }, [isResolving, isInstitutionStudent, dispatch]);

  if (isResolving) {
    return <PageLoader />;
  }

  if (isInstitutionStudent) {
    return <Navigate to="/courses/my" replace />;
  }

  return children ? <>{children}</> : <Outlet />;
}
