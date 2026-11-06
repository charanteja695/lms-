import type { DashboardFilters, DashboardKey } from "@/modules/analytics/common/types";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** The permission that unlocks each platform-wide dashboard; `analytics.view` unlocks them all (analytics-service policy). */
const DOMAIN_PERMISSION: Partial<Record<DashboardKey, string>> = {
  content: "content.review", exam_integrity: "exams.manage", support: "support.manage", hiring: "careers.manage", ai_usage: "ai.manage", billing: "billing.manage",
};

export interface DashboardAccess {
  key: DashboardKey;
  /** Platform viewers may filter by organisation; members always see their own, sent explicitly (a saved report needs it). */
  platform: boolean;
  fixed: DashboardFilters;
}

/** Which dashboards this person may open, and how — from the server's permission list, not the role. */
export function useAnalyticsRights(): { dashboards: DashboardAccess[]; isPlatform: boolean } {
  const { user } = useAuth();
  const { can, holds, organizationType } = useCan();
  const ownOrg = user?.institution?.organization_id;
  const own = holds("analytics.own") && Boolean(ownOrg);
  const isInstitution = own && organizationType === "institution";
  const isEmployer = own && organizationType === "employer";
  const canPlatform = (key: DashboardKey) => can("analytics.view") || (DOMAIN_PERMISSION[key] ? can(DOMAIN_PERMISSION[key]) : false);

  const dashboards: DashboardAccess[] = [];
  for (const key of ["institution", "content", "exam_integrity", "support", "hiring", "ai_usage", "billing"] as DashboardKey[]) {
    if (canPlatform(key)) dashboards.push({ key, platform: true, fixed: {} });
    else if (key === "institution" && isInstitution) dashboards.push({ key, platform: false, fixed: { organization_id: ownOrg } });
    else if (key === "hiring" && isInstitution) dashboards.push({ key, platform: false, fixed: { organization_id: ownOrg } });
    else if (key === "hiring" && isEmployer) dashboards.push({ key, platform: false, fixed: { employer_id: ownOrg } });
  }
  return { dashboards, isPlatform: dashboards.some((d) => d.platform) };
}
