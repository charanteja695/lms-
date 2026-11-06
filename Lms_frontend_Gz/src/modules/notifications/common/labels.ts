import type { DeliveryStatus, Template } from "@/modules/notifications/common/types";

export const CHANNEL_LABELS: Record<Template["channel"], string> = { in_app: "In-app", email: "Email" };

export const DELIVERY_STATUS_LABELS: Record<DeliveryStatus, string> = { pending: "Pending", sent: "Sent", failed: "Failed" };

export const DELIVERY_STATUS_TONES = { pending: "amber", sent: "green", failed: "red" } as const satisfies Record<DeliveryStatus, string>;
