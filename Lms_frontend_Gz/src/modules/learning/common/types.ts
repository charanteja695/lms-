/** Mirrors learning-service's app/domain/enums.py. */
export type BatchStatus = "active" | "archived";

export type EnrollmentStatus = "active" | "completed" | "withdrawn";

/** Mirrors catalog-service's item types, as carried onto learning-service's own topic item refs. */
export type ItemType = "video" | "pdf" | "notes" | "practice" | "quiz";
