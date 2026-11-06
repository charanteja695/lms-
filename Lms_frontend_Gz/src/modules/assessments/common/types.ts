/** Mirrors assessment-service's enums (see docs/API.md). */
export type QuestionType = "mcq_single" | "mcq_multi" | "true_false" | "fill_in" | "match" | "ordering" | "coding" | "sql" | "subjective" | "file_submission";

export type QuestionStatus = "active" | "retired";

export type VersionStatus = "draft" | "in_review" | "published" | "superseded";

export type Bloom = "remember" | "understand" | "apply" | "analyze" | "evaluate" | "create";

export type TestKind = "topic" | "module" | "final" | "practice" | "hiring";

export type TestStatus = "draft" | "in_review" | "published" | "retired";

export type TimeMode = "overall" | "per_section";

export type ScoreCounting = "highest" | "latest";

export type ResultVisibility = "immediate" | "after_window" | "manual";

export type ReviewPolicy = "none" | "answers";

export type ProctoringLevel = "none" | "basic" | "strict";

export type SlotType = "fixed" | "pool";

export type AttemptStatus = "not_started" | "in_progress" | "paused" | "submitted" | "grading" | "graded";

export type AttemptResult = "pending" | "passed" | "failed" | "invalidated";

export type IntegrityStatus = "not_required" | "pending" | "clear" | "flagged" | "under_review" | "reviewed_ok" | "invalidated";
