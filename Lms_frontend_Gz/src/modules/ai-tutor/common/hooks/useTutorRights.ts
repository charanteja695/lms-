import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** From the server's permission list (tutor.chat / tutor.faq.manage / content.author / support.manage / ai.manage). */
export function useTutorRights() {
  const { can, holds, acts } = useCan();
  const author = can("content.author");
  const support = can("support.manage");
  const ai = can("ai.manage");
  const isStaff = acts("tutor_faq.view", "tutor.faq.manage");
  const faq = (action: "create" | "update" | "delete") => author || support || acts(`tutor_faq.${action}`, "tutor.faq.manage");
  return {
    canChat: holds("tutor.chat"),
    canManageFaq: isStaff || author || support,
    /** One action each, as the server checks it (the Tutor FAQ page's cells). */
    canCreateFaq: faq("create"),
    canEditFaq: faq("update"),
    canArchiveFaq: faq("delete"),
    canSeeInsights: author || support,
    canSeeIndex: author || support || ai,
    canReindex: ai,
    canSeeEscalations: support,
    isStaff,
    author,
    support,
  };
}

