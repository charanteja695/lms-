/** Mirrors analytics-service (docs/API.md). Every dashboard is a flat set of totals for the trailing `days`. */
export type DashboardKey = "institution" | "content" | "exam_integrity" | "support" | "hiring" | "ai_usage" | "billing";

export interface DashboardFilters {
  organization_id?: string;
  employer_id?: string;
}

/** Totals are numbers (or null for a rate with nothing to divide); breakdowns are name -> count maps. */
export type DashboardData = { since: string; until: string } & Record<string, number | string | null | Record<string, number>>;

export type ReportFrequency = "daily" | "weekly" | "monthly";
export type ReportFormat = "csv" | "json";
export type ReportRunStatus = "pending" | "running" | "ready" | "failed";

export interface Report {
  report_id: string;
  name: string;
  dashboard: DashboardKey;
  filters: DashboardFilters;
  format: ReportFormat;
  frequency: ReportFrequency;
  next_run_at: string;
  active: boolean;
  created_at: string;
}

export interface ReportRun {
  run_id: string;
  status: ReportRunStatus;
  period_start: string | null;
  period_end: string | null;
  row_count: number | null;
  content_type: string | null;
  error: string | null;
  dashboard_snapshot: Record<string, unknown> | null;
  generated_at: string | null;
  created_at: string;
}
