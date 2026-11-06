import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { SectionTabs } from "@/shared/ui";

/** Staff screens: Student Progress & Live sessions, cases needing decision, and media audit log. */
export function ProctoringTabs() {
  const { can, isSuperAdmin } = useCan();
  const canSeeAudit = isSuperAdmin || can("exams.manage");
  return (
    <SectionTabs
      tabs={[
        { to: "/proctoring/monitor", label: "Progress of Student", icon: "chart" },
        { to: "/proctoring/cases", label: "Integrity cases", icon: "shield" },
        { to: "/proctoring/audit", label: "Media audit log", icon: "fileText", show: canSeeAudit },
      ]}
    />
  );
}
