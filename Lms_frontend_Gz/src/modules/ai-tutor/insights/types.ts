import type { Id, IsoDateTime } from "@/core/api/types";

export interface FeedbackSummary {
  course_id: Id;
  up: number;
  down: number;
  down_rate: number | null;
}

export interface DownvotedAnswer {
  message_id: Id;
  question: string | null;
  answer: string;
  kind: string;
  comment: string | null;
  at: IsoDateTime;
}

export interface EvalSet {
  eval_set_id: Id;
  course_id: Id;
  name: string;
  created_at: IsoDateTime;
}

export interface EvalCase {
  case_id: Id;
  question: string;
  expected_item_ids: Id[];
}

export interface EvalRunResult {
  question: string;
  hit: boolean;
  rank: number | null;
  top?: Array<{ item_id?: Id; item_title?: string; score?: number }>;
}

export interface EvalRun {
  run_id: Id;
  version_id: Id;
  method: "dense" | "lexical" | string;
  top_k: number;
  case_count: number;
  hits: number;
  hit_rate: number;
  mrr: number;
  results: EvalRunResult[];
  created_at: IsoDateTime;
}

export interface EvalSetDetail {
  eval_set: EvalSet;
  cases: EvalCase[];
  runs: EvalRun[];
}

export interface IndexVersion {
  version_id: Id;
  retired: boolean;
  chunks: number;
  embedded_chunks: number;
  job_status: string | null;
  job_attempts: number;
  last_error: string | null;
}
