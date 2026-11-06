import type { CourseRequestStatus, SubscriptionStatus } from "@/modules/subscriptions/common/types";
import type { BadgeTone } from "@/shared/ui";

export const COURSE_REQUEST_STATUS_LABELS: Record<CourseRequestStatus, string> = {
  submitted: "Submitted",
  approved: "Approved",
  rejected: "Rejected",
};

export const COURSE_REQUEST_STATUS_TONES: Record<CourseRequestStatus, BadgeTone> = {
  submitted: "amber",
  approved: "green",
  rejected: "red",
};

export const SUBSCRIPTION_STATUS_LABELS: Record<SubscriptionStatus, string> = {
  active: "Active",
  expired: "Expired",
  cancelled: "Cancelled",
};

export const SUBSCRIPTION_STATUS_TONES: Record<SubscriptionStatus, BadgeTone> = {
  active: "green",
  expired: "gray",
  cancelled: "red",
};
