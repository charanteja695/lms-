import { SUBSCRIPTION_STATUS_LABELS, SUBSCRIPTION_STATUS_TONES } from "@/modules/subscriptions/common/labels";
import type { SubscriptionStatus } from "@/modules/subscriptions/common/types";
import { Badge } from "@/shared/ui";

export function SubscriptionStatusBadge({ status }: { status: SubscriptionStatus }) {
  return <Badge tone={SUBSCRIPTION_STATUS_TONES[status]}>{SUBSCRIPTION_STATUS_LABELS[status]}</Badge>;
}
