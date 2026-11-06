import type { Id, IsoDateTime } from "@/core/api/types";
import type { AnalysisStatus, CaseStatus, SnapshotKind } from "@/modules/proctoring/common/types";

export interface ProctorCase {
  case_id: Id;
  session_id: Id;
  attempt_id: Id;
  test_id: Id;
  test_title: string | null;
  user_id: Id;
  organization_id: Id | null;
  status: CaseStatus;
  severity: string;
  risk_score: number;
  reasons: string[];
  assigned_to: Id | null;
  decision: string | null;
  decided_by: Id | null;
  decided_at: IsoDateTime | null;
  decision_note: string | null;
  appeal_status: string;
  appeal_reason: string | null;
  appealed_at: IsoDateTime | null;
  appeal_decided_by: Id | null;
  appeal_note: string | null;
  overdue: boolean;
  can_appeal: boolean;
  created_at: IsoDateTime;
}

export interface CaseSnapshot {
  snapshot_id: Id;
  kind: SnapshotKind;
  sequence: number;
  taken_at: IsoDateTime;
  analysis_status: AnalysisStatus;
  skip_reason: string | null;
  flagged: boolean;
  findings: Record<string, unknown>[] | null;
}

export interface TimelineEntry {
  at: IsoDateTime;
  type: string;
  source: "client" | "ai" | "system" | "staff";
  points: number;
}

export interface CaseReport {
  level: string;
  risk_score: number;
  risk_breakdown: Record<string, number>;
  critical: boolean;
  terminated: boolean;
  event_counts: Record<string, number>;
  timeline: TimelineEntry[];
  snapshots: Record<string, number>;
  flagged_snapshots: Id[];
  ai_analysis: AnalysisStatus;
  started_at: IsoDateTime | null;
  ended_at: IsoDateTime | null;
}

export interface ProctorCaseDetail extends ProctorCase {
  report: CaseReport;
  snapshots: CaseSnapshot[];
}

export interface StudentCase {
  case_id: Id;
  attempt_id: Id;
  test_id: Id;
  test_title: string | null;
  status: CaseStatus;
  decision: string | null;
  decision_note: string | null;
  appeal_status: string;
  can_appeal: boolean;
  created_at: IsoDateTime;
}

export interface MediaAccess {
  snapshot_id: Id;
  session_id: Id;
  viewer_user_id: Id;
  reason: string;
  created_at: IsoDateTime;
}

export interface CaseFilters {
  test_id?: string;
  status?: CaseStatus;
  overdue?: boolean;
}
