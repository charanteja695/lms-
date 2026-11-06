/** Mirrors catalog-service's app/domain/enums.py. */
export type ContentStatus = "draft" | "in_review" | "published" | "archived";

export type ItemType = "video" | "pdf" | "notes" | "practice" | "quiz";

export type UnlockMode = "sequential" | "drip";

export type ReviewAction = "submitted" | "approved" | "rejected" | "retired";
