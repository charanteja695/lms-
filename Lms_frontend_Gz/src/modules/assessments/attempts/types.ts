import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { AttemptResult, AttemptStatus, IntegrityStatus, ProctoringLevel, TestKind, TimeMode } from "@/modules/assessments/common/types";

export interface MyTest {
  test_id: Id;
  title: string;
  kind: TestKind;
  description: string | null;
  time_mode: TimeMode;
  duration_minutes: number | null;
  pass_mark_percent: number;
  question_count: number | null;
  total_marks: number | null;
  proctoring_level: ProctoringLevel;
  can_start: boolean;
  reason: string | null;
  message: string | null;
  attempts_used: number;
  attempts_left: number | null;
  next_available_at: IsoDateTime | null;
  opens_at: IsoDateTime | null;
  open_attempt_id: Id | null;
  best_percent: number | null;
}

export interface MyTestFilters {
  kind?: TestKind;
  target_id?: string;
}

export interface AttemptListItem {
  attempt_id: Id;
  test_id: Id;
  user_id: Id;
  organization_id: Id | null;
  attempt_no: number;
  status: AttemptStatus;
  result: AttemptResult;
  score: number | null;
  max_score: number | null;
  percent: number | null;
  integrity_status: IntegrityStatus;
  plagiarism_flagged: boolean;
  started_at: IsoDateTime | null;
  submitted_at: IsoDateTime | null;
  results_visible_at: IsoDateTime | null;
}

export interface AttemptFilters {
  test_id?: string;
  user_id?: string;
  status?: AttemptStatus;
  result?: AttemptResult;
  integrity_status?: IntegrityStatus;
  plagiarism_flagged?: boolean;
  sort_order?: SortOrder;
}

export interface AttemptEvent {
  event_type: string;
  actor_user_id: Id | null;
  ip_address: string | null;
  detail: Record<string, unknown> | null;
  created_at: IsoDateTime;
}
