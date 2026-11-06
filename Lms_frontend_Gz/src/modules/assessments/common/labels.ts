import type {
  AttemptResult,
  AttemptStatus,
  Bloom,
  IntegrityStatus,
  ProctoringLevel,
  QuestionType,
  ResultVisibility,
  ReviewPolicy,
  ScoreCounting,
  TestKind,
  TestStatus,
  VersionStatus,
} from "@/modules/assessments/common/types";
import type { BadgeTone } from "@/shared/ui";

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  mcq_single: "Single choice",
  mcq_multi: "Multiple choice",
  true_false: "True / False",
  fill_in: "Fill in the blanks",
  match: "Match the pairs",
  ordering: "Ordering",
  coding: "Coding",
  sql: "SQL",
  subjective: "Subjective",
  file_submission: "File submission",
};

export const VERSION_STATUS_LABELS: Record<VersionStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  published: "Published",
  superseded: "Superseded",
};

export const VERSION_STATUS_TONES: Record<VersionStatus, BadgeTone> = {
  draft: "gray",
  in_review: "amber",
  published: "green",
  superseded: "gray",
};

export const BLOOM_LABELS: Record<Bloom, string> = {
  remember: "Remember",
  understand: "Understand",
  apply: "Apply",
  analyze: "Analyze",
  evaluate: "Evaluate",
  create: "Create",
};

export const TEST_KIND_LABELS: Record<TestKind, string> = {
  topic: "Topic test",
  module: "Module test",
  final: "Final test",
  practice: "Practice test",
  hiring: "Hiring assessment",
};

export const TEST_STATUS_LABELS: Record<TestStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  published: "Published",
  retired: "Retired",
};

export const TEST_STATUS_TONES: Record<TestStatus, BadgeTone> = {
  draft: "gray",
  in_review: "amber",
  published: "green",
  retired: "red",
};

export const RESULT_VISIBILITY_LABELS: Record<ResultVisibility, string> = {
  immediate: "Immediately after submitting",
  after_window: "When the exam window closes",
  manual: "Released manually",
};

export const REVIEW_POLICY_LABELS: Record<ReviewPolicy, string> = {
  none: "Score only",
  answers: "Score with correct answers",
};

export const PROCTORING_LEVEL_LABELS: Record<ProctoringLevel, string> = {
  none: "None",
  basic: "Basic",
  strict: "Strict",
};

export const SCORE_COUNTING_LABELS: Record<ScoreCounting, string> = {
  highest: "Highest attempt",
  latest: "Latest attempt",
};

export const ATTEMPT_STATUS_LABELS: Record<AttemptStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  paused: "Paused",
  submitted: "Submitted",
  grading: "Grading",
  graded: "Graded",
};

export const ATTEMPT_STATUS_TONES: Record<AttemptStatus, BadgeTone> = {
  not_started: "gray",
  in_progress: "blue",
  paused: "amber",
  submitted: "amber",
  grading: "amber",
  graded: "green",
};

export const ATTEMPT_RESULT_LABELS: Record<AttemptResult, string> = {
  pending: "Pending",
  passed: "Passed",
  failed: "Failed",
  invalidated: "Invalidated",
};

export const ATTEMPT_RESULT_TONES: Record<AttemptResult, BadgeTone> = {
  pending: "gray",
  passed: "green",
  failed: "red",
  invalidated: "red",
};

export const INTEGRITY_STATUS_LABELS: Record<IntegrityStatus, string> = {
  not_required: "Not required",
  pending: "Pending",
  clear: "Clear",
  flagged: "Flagged",
  under_review: "Under review",
  reviewed_ok: "Reviewed — OK",
  invalidated: "Invalidated",
};

export const INTEGRITY_STATUS_TONES: Record<IntegrityStatus, BadgeTone> = {
  not_required: "gray",
  pending: "gray",
  clear: "green",
  flagged: "red",
  under_review: "amber",
  reviewed_ok: "green",
  invalidated: "red",
};
