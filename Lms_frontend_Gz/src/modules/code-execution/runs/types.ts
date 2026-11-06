import type { Id, IsoDateTime } from "@/core/api/types";
import type { JobStatus } from "@/modules/code-execution/common/types";

export interface Run {
  run_id: Id;
  language: string;
  status: JobStatus;
  /** "ok" once it ran cleanly; otherwise a failure kind such as "compilation_error", "runtime_error", "time_limit_exceeded". */
  outcome: string | null;
  stdout: string | null;
  stderr: string | null;
  compile_output: string | null;
  message: string | null;
  time_ms: number | null;
  memory_kb: number | null;
  exit_code: number | null;
  created_at: IsoDateTime;
  finished_at: IsoDateTime | null;
}

export interface RunCreateBody {
  language: string;
  source: string;
  stdin?: string;
  /** SQL only: run the query against this problem's schema and sample data. */
  problem_id?: string | null;
}
