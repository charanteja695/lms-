import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

/**
 * Who sees what here, from the server's permission list (ai-gateway re-checks every call):
 * `ai.manage` runs the platform's AI (any organisation's usage and limits, models, prompts, logs);
 * `ai.usage.own` (institution head/staff by default) sees their own institution's usage and limits only.
 */
export function useAiRights(): { isManager: boolean; ownOrganizationId: string | null } {
  const { user } = useAuth();
  const { can, holds } = useCan();
  const own = holds("ai.usage.own") ? (user?.institution?.organization_id ?? null) : null;
  return { isManager: can("ai.manage"), ownOrganizationId: own };
}
