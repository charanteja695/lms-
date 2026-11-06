import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** Mirrors certificate-service's own split: content.author writes drafts, content.review activates/archives (super admin both). */
export function useTemplateRights() {
  const { can } = useCan();
  return { canAuthor: can("content.author"), canPublish: can("content.review") };
}

