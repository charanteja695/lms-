import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { JobStatus, Verdict } from "@/modules/code-execution/common/types";
import type { CaseResult } from "@/modules/code-execution/submissions/types";

export interface ReviewSubmission {
  submission_id: Id;
  problem_id: Id;
  language: string;
  status: JobStatus;
  verdict: Verdict | null;
  score: number;
  passed_count: number;
  total_count: number;
  created_at: IsoDateTime;
  source: string;
  time_ms: number | null;
  memory_kb: number | null;
  compile_output: string | null;
  message: string | null;
  judged_at: IsoDateTime | null;
  results: CaseResult[];
  user_id: Id;
  organization_id: Id | null;
  /** Set only for exam-lane submissions (assessment-service's attempt reference). */
  reference: string | null;
  flagged: boolean;
  similarity_percent: number | null;
  similar_to_submission_id: Id | null;
}

export interface ReviewSubmissionListItem {
  submission_id: Id;
  problem_id: Id;
  language: string;
  status: JobStatus;
  verdict: Verdict | null;
  score: number;
  passed_count: number;
  total_count: number;
  created_at: IsoDateTime;
  user_id: Id;
  reference: string | null;
  flagged: boolean;
  similarity_percent: number | null;
  similar_to_submission_id: Id | null;
}

export interface ReviewFilters {
  problem_id?: string;
  status?: JobStatus;
  verdict?: Verdict;
  user_id?: string;
  reference?: string;
  flagged?: boolean;
  sort_order?: SortOrder;
}

export interface SimilarMatch {
  submission_id: Id;
  user_id: Id;
  similarity_percent: number;
  verdict: Verdict | null;
  created_at: IsoDateTime;
}
