import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** Mirrors notification-service: everyone has an inbox and email preferences; only a super admin edits templates and retries deliveries. */
export function useNotificationRights() {
  const { isSuperAdmin } = useCan();
  return { isSuperAdmin };
}

