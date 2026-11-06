import { useInterviewRights } from "@/modules/ai-interview/common/hooks/useInterviewRights";
import { SectionTabs } from "@/shared/ui";

/** The staff screens (screening interviews, plans, appeals) for those who may open them. */
export function InterviewTabs() {
  const { isEmployer, isCareersManager } = useInterviewRights();
  const reviews = isEmployer || isCareersManager;
  return (
    <SectionTabs
      tabs={[
        { to: "/interviews/screening", label: "Screening interviews", icon: "users", show: reviews },
        { to: "/interviews/plans", label: "Plans", icon: "fileText" },
        { to: "/interviews/appeals", label: "Appeals", icon: "alert", show: reviews },
      ]}
    />
  );
}
