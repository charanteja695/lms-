import { Id, IsoDateTime } from "@/core/api/types";

export type JobType = "user_export" | "admin_export" | "institution_export" | "employer_export" | "user_import";

export interface ImportSummary {
  dry_run: boolean;
  mode: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  created: number;
}

export type JobStatus = "queued" | "running" | "completed" | "failed" | "expired";

export interface Job {
  job_id: Id;
  type: JobType;
  status: JobStatus;
  row_count: number | null;
  file_name: string | null;
  file_size_bytes: number | null;
  error_message: string | null;
  download_url: string | null;
  import_summary: ImportSummary | null;
  created_time: IsoDateTime;
  started_time: IsoDateTime | null;
  finished_time: IsoDateTime | null;
  expires_time: IsoDateTime | null;
}
