import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { SubscriptionStatus } from "@/modules/subscriptions/common/types";

export interface Subscription {
  subscription_id: Id;
  organization_id: Id;
  course_id: Id;
  seats_total: number;
  seats_used: number;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  status: SubscriptionStatus;
  cancelled_at: IsoDateTime | null;
  cancelled_reason: string | null;
  created_at: IsoDateTime;
}

export interface SubscriptionFilters {
  status?: SubscriptionStatus;
  sort_order?: SortOrder;
}
