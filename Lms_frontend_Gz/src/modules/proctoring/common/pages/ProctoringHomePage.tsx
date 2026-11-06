import { Navigate } from "react-router-dom";

import { useCan } from "@/modules/user-management/common/permissions/useCan";

/**
 * A student's only proctoring screen is their own cases; everyone else with the "proctoring"
 * section (institution staff/head, employer members, exam managers) lands on live monitoring.
 * One nav item can't point to two routes, so it points here and this decides.
 */
export function ProctoringHomePage() {
  const { holds } = useCan();
  return <Navigate to={holds("proctoring.take") ? "/proctoring/my-cases" : "/proctoring/monitor"} replace />;
}
