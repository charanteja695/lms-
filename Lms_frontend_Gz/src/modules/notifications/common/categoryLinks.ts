import type { Section } from "@/modules/user-management/common/permissions/types";
import type { Category } from "@/modules/notifications/common/types";

/** Where "Open" goes for each category: the module that owns it. Shown only if that section is open to the person. */
export const CATEGORY_LINKS: Record<Category, { section: Section; to: string; label: string }> = {
  enrollment: { section: "learning", to: "/my-learning", label: "My learning" },
  learning: { section: "learning", to: "/my-learning", label: "My learning" },
  subscription: { section: "subscriptions", to: "/subscriptions", label: "Subscriptions" },
};
