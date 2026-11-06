import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { JobStatus, Verdict } from "@/modules/code-execution/common/types";

export interface CaseResult {
  position: number;
  is_sample: boolean;
  verdict: Verdict;
  time_ms: number | null;
  memory_kb: number | null;
  message: string | null;
  /** Only ever populated for a sample case — a hidden case never reveals its data, even to its own author. */
  input: string | null;
  expected: string | null;
  actual: string | null;
}

export interface Submission {
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
}

export interface SubmissionListItem {
  submission_id: Id;
  problem_id: Id;
  language: string;
  status: JobStatus;
  verdict: Verdict | null;
  score: number;
  passed_count: number;
  total_count: number;
  created_at: IsoDateTime;
}

export interface SubmissionFilters {
  problem_id?: string;
  status?: JobStatus;
  verdict?: Verdict;
  sort_order?: SortOrder;
}

export interface SubmissionCreateBody {
  language: string;
  source: string;
}
