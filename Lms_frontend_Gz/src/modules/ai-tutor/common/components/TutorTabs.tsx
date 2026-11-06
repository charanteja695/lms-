import { useTutorRights } from "@/modules/ai-tutor/common/hooks/useTutorRights";
import { SectionTabs } from "@/shared/ui";

/** The staff-side tutor screens this person can open. */
export function TutorTabs() {
  const rights = useTutorRights();
  return (
    <SectionTabs
      tabs={[
        { to: "/tutor/faqs", label: "FAQ", icon: "helpCircle", show: rights.canManageFaq },
        { to: "/tutor/insights", label: "Course insights", icon: "layers", show: rights.canSeeIndex },
        { to: "/tutor/escalations", label: "Escalations", icon: "users", show: rights.canSeeEscalations },
      ]}
    />
  );
}
