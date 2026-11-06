import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { SectionTabs } from "@/shared/ui";

/** Problems for everyone in the module; the submission review for reviewers and languages for a super admin. */
export function CodeTabs() {
  const { can, isSuperAdmin } = useCan();
  const isSuper = isSuperAdmin;
  const canReview = isSuper || ["content.author", "content.review", "exams.manage"].some(can);
  return (
    <SectionTabs
      tabs={[
        { to: "/problems", label: "Problems", icon: "terminal" },
        { to: "/review/submissions", label: "Review submissions", icon: "alert", show: canReview },
        { to: "/languages", label: "Languages", icon: "edit", show: isSuper },
      ]}
    />
  );
}
