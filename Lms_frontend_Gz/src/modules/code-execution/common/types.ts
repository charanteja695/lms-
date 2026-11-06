/** Mirrors code-execution-service's enums. */
export type LanguageKind = "program" | "sql";

export type Difficulty = "easy" | "medium" | "hard";

export type ProblemType = "code" | "sql";

export type ProblemStatus = "draft" | "published" | "retired";

/** A run's or submission's own lifecycle, before it has a verdict. */
export type JobStatus = "queued" | "running" | "completed";

export type Verdict =
  | "accepted"
  | "wrong_answer"
  | "time_limit_exceeded"
  | "memory_limit_exceeded"
  | "runtime_error"
  | "compilation_error"
  | "output_limit_exceeded"
  | "internal_error";

export type CompareMode = "exact" | "trim" | "token" | "float" | "rows_ordered" | "rows_unordered";
