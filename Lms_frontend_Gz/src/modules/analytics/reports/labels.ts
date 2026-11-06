import type { ReportFormat, ReportFrequency, ReportRunStatus } from "@/modules/analytics/common/types";

export const FREQUENCY_LABELS: Record<ReportFrequency, string> = { daily: "Daily", weekly: "Weekly", monthly: "Monthly" };

export const FORMAT_LABELS: Record<ReportFormat, string> = { csv: "CSV", json: "JSON" };

export const RUN_STATUS_LABELS: Record<ReportRunStatus, string> = { pending: "Pending", running: "Running", ready: "Ready", failed: "Failed" };

export const RUN_STATUS_TONES = { pending: "gray", running: "amber", ready: "green", failed: "red" } as const satisfies Record<ReportRunStatus, string>;
