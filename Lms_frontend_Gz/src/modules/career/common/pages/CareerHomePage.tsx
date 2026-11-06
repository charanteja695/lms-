import { Navigate } from "react-router-dom";

import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** Students build their profile and resumes; staff and careers managers look students up (read only). */
export function CareerHomePage() {
  const { holds } = useCan();
  return <Navigate to={holds("career.profile") ? "/career/profile" : "/career/students"} replace />;
}
