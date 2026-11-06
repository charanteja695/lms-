import type { CompareMode, Difficulty, JobStatus, ProblemStatus, ProblemType, Verdict } from "@/modules/code-execution/common/types";
import type { BadgeTone } from "@/shared/ui";

export const PROBLEM_STATUS_LABELS: Record<ProblemStatus, string> = {
  draft: "Draft",
  published: "Published",
  retired: "Retired",
};

export const PROBLEM_STATUS_TONES: Record<ProblemStatus, BadgeTone> = {
  draft: "gray",
  published: "green",
  retired: "red",
};

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

export const DIFFICULTY_TONES: Record<Difficulty, BadgeTone> = {
  easy: "green",
  medium: "amber",
  hard: "red",
};

export const PROBLEM_TYPE_LABELS: Record<ProblemType, string> = {
  code: "Code",
  sql: "SQL",
};

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
};

export const VERDICT_LABELS: Record<Verdict, string> = {
  accepted: "Accepted",
  wrong_answer: "Wrong answer",
  time_limit_exceeded: "Time limit exceeded",
  memory_limit_exceeded: "Memory limit exceeded",
  runtime_error: "Runtime error",
  compilation_error: "Compilation error",
  output_limit_exceeded: "Output limit exceeded",
  internal_error: "Internal error",
};

export const VERDICT_TONES: Record<Verdict, BadgeTone> = {
  accepted: "green",
  wrong_answer: "red",
  time_limit_exceeded: "amber",
  memory_limit_exceeded: "amber",
  runtime_error: "red",
  compilation_error: "red",
  output_limit_exceeded: "amber",
  internal_error: "gray",
};

export const COMPARE_MODE_LABELS: Record<CompareMode, string> = {
  exact: "Exact match",
  trim: "Trim whitespace",
  token: "Token-by-token",
  float: "Floating point (tolerance)",
  rows_ordered: "Result rows, in order",
  rows_unordered: "Result rows, any order",
};
