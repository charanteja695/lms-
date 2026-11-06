import type { Id, IsoDateTime } from "@/core/api/types";
import type { AttemptStatus, ProctoringLevel, QuestionType, TestKind, TimeMode } from "@/modules/assessments/common/types";

export interface PaperQuestion {
  question_id: Id;
  position: number;
  section_id: Id;
  section_position: number;
  question_type: QuestionType;
  text: string;
  marks: number;
  body: Record<string, unknown>;
  answer: Record<string, unknown> | null;
}

export interface SectionState {
  section_id: Id;
  position: number;
  title: string;
  time_limit_minutes: number | null;
  started_at: IsoDateTime | null;
  deadline_at: IsoDateTime | null;
  finished_at: IsoDateTime | null;
  is_current: boolean;
}

export interface AttemptState {
  attempt_id: Id;
  test_id: Id;
  test_title: string;
  test_kind: TestKind;
  status: AttemptStatus;
  attempt_no: number;
  proctoring_level: ProctoringLevel;
  time_mode: TimeMode;
  started_at: IsoDateTime | null;
  deadline_at: IsoDateTime | null;
  remaining_seconds: number | null;
  server_time: IsoDateTime;
  resume_count: number;
  opens_at: IsoDateTime | null;
  submitted_at: IsoDateTime | null;
  submit_reason: string | null;
  results_released: boolean;
  total_questions: number;
  sections: SectionState[];
}

export interface AttemptPaper {
  attempt: AttemptState;
  questions: PaperQuestion[];
}

export interface SavedAnswer {
  question_id: Id;
  status: "saved" | "stale" | "rejected";
  revision: number;
  error: Record<string, unknown> | null;
}
