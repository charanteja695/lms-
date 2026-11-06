import { Navigate } from "react-router-dom";

import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";

/** Students land on their own tickets; agents (staff, exam team, support managers) on their queue. */
export function SupportHomePage() {
  const { isStudent } = useSupportRights();
  return <Navigate to={isStudent ? "/support/my-tickets" : "/support/queue"} replace />;
}
