import { Navigate } from "react-router-dom";

import { useTutorRights } from "@/modules/ai-tutor/common/hooks/useTutorRights";

/** One nav item for every "ai_tutor" section holder; each lands on the first screen they can actually open. */
export function TutorHomePage() {
  const rights = useTutorRights();
  const to = rights.canChat ? "/tutor/chat" : rights.canManageFaq ? "/tutor/faqs" : "/tutor/insights";
  return <Navigate to={to} replace />;
}
