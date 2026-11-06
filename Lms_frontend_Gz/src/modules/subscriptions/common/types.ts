/** Mirrors subscription-service's app/domain/enums.py. */
export type CourseRequestStatus = "submitted" | "approved" | "rejected";

/** approved course request -> active subscription -> expired (term ended) or cancelled early. */
export type SubscriptionStatus = "active" | "expired" | "cancelled";
