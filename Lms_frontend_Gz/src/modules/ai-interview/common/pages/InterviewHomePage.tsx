import { Navigate } from "react-router-dom";

import { useInterviewRights } from "@/modules/ai-interview/common/hooks/useInterviewRights";

export function InterviewHomePage() {
  const { isStudent, isEmployer } = useInterviewRights();
  return <Navigate to={isStudent ? "/interviews/practice" : isEmployer ? "/interviews/screening" : "/interviews/plans"} replace />;
}
