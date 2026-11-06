import type { Id } from "@/core/api/types";

export interface TestIssue {
  field: string;
  code: string;
  message: string;
}

/** What a course test holds against what its kind needs (0 required: no rule). */
export interface TestComposition {
  multiple_choice: number;
  programs: number;
  required_multiple_choice: number;
  required_programs: number;
}

export interface TestValidation {
  valid: boolean;
  issues: TestIssue[];
  total_marks: number | null;
  question_count: number | null;
  composition: TestComposition;
}

export interface TestCompositionItem extends TestComposition {
  test_id: string;
  valid: boolean;
  issue_count: number;
}

export interface TestAnalytics {
  attempts: Record<string, number>;
  graded: number;
  average_percent: number | null;
  pass_rate_percent: number | null;
  average_minutes: number | null;
  distribution: Record<string, unknown>[];
  plagiarism_flagged: number;
  integrity_pending: number;
  questions: Record<string, unknown>[];
}

export interface PlagiarismItem {
  attempt_id: Id;
  user_id: Id;
  question_id: Id;
  language: string;
  verdict: string | null;
  similarity_percent: number | null;
  similar_to_submission_id: Id | null;
  code_submission_id: Id | null;
}
