import { SectionTabs } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** Issued certificates for everyone here; their templates for authors and reviewers. */
export function CertificateTabs() {
  const { can } = useCan();
  const canSeeTemplates = can("content.author") || can("content.review");
  return (
    <SectionTabs
      tabs={[
        { to: "/certificates/issued", label: "Issued", icon: "archive" },
        { to: "/certificates/templates", label: "Templates", icon: "fileText", show: canSeeTemplates },
      ]}
    />
  );
}
