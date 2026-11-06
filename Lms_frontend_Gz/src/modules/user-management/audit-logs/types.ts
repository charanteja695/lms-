import { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import { InstitutionRef, UserRef } from "@/modules/user-management/common/types";

export type AuditCategory = "auth" | "user" | "institution" | "employer" | "job";

export interface AuditLog {
  audit_log_id: Id;
  time: IsoDateTime;
  action: string;
  category: string;
  actor: UserRef | null;
  target: { type: string; id: Id | null; name: string | null } | null;
  institution: InstitutionRef | null;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  details: Record<string, unknown> | null;
}

export interface AuditLogFilters {
  search_text?: string;
  category?: AuditCategory;
  action?: string;
  actor_user_id?: Id;
  user_id?: Id;
  organization_id?: Id;
  created_from?: string;
  created_to?: string;
  sort_order?: SortOrder;
}
