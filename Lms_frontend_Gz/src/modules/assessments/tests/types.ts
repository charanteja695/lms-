import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { ProctoringLevel, ResultVisibility, ReviewPolicy, ScoreCounting, TestKind, TestStatus, TimeMode } from "@/modules/assessments/common/types";
import type { Section, SectionInput } from "@/modules/assessments/tests/sectionTypes";

export interface Test {
  test_id: Id;
  title: string;
  kind: TestKind;
  status: TestStatus;
  target_type: string | null;
  target_id: Id | null;
  organization_id: Id | null;
  time_mode: TimeMode;
  duration_minutes: number | null;
  pass_mark_percent: number;
  max_attempts: number;
  proctoring_level: ProctoringLevel;
  total_marks: number | null;
  question_count: number | null;
  created_at: IsoDateTime;
  published_at: IsoDateTime | null;
  description: string | null;
  instructions: string | null;
  cooldown_hours: number;
  score_counting: ScoreCounting;
  negative_marking_percent: number;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  result_visibility: ResultVisibility;
  review_policy: ReviewPolicy;
  proctoring_screen_share: boolean;
  requires_schedule: boolean;
  review_note: string | null;
  created_by: Id;
  updated_at: IsoDateTime;
  sections: Section[];
}

export interface TestListItem {
  test_id: Id;
  title: string;
  kind: TestKind;
  status: TestStatus;
  target_type: string | null;
  target_id: Id | null;
  organization_id: Id | null;
  time_mode: TimeMode;
  duration_minutes: number | null;
  pass_mark_percent: number;
  max_attempts: number;
  proctoring_level: ProctoringLevel;
  total_marks: number | null;
  question_count: number | null;
  created_at: IsoDateTime;
  published_at: IsoDateTime | null;
}

export interface TestFilters {
  kind?: TestKind;
  target_id?: string;
  /** Several targets, comma separated (e.g. every topic of a course). */
  target_ids?: string;
  status?: TestStatus;
  search?: string;
  sort_order?: SortOrder;
}

export interface TestCreateBody {
  title: string;
  kind: TestKind;
  target_id?: string | null;
  description?: string | null;
  instructions?: string | null;
  time_mode?: TimeMode;
  duration_minutes?: number | null;
  pass_mark_percent?: number;
  max_attempts?: number;
  cooldown_hours?: number;
  score_counting?: ScoreCounting;
  negative_marking_percent?: number;
  shuffle_questions?: boolean;
  shuffle_options?: boolean;
  result_visibility?: ResultVisibility;
  review_policy?: ReviewPolicy;
  proctoring_level?: ProctoringLevel;
  proctoring_screen_share?: boolean;
  requires_schedule?: boolean;
  sections?: SectionInput[];
}

export interface TestUpdateBody {
  title?: string;
  description?: string | null;
  instructions?: string | null;
  kind?: TestKind;
  target_id?: string | null;
  time_mode?: TimeMode;
  duration_minutes?: number | null;
  pass_mark_percent?: number;
  max_attempts?: number;
  cooldown_hours?: number;
  score_counting?: ScoreCounting;
  negative_marking_percent?: number;
  shuffle_questions?: boolean;
  shuffle_options?: boolean;
  result_visibility?: ResultVisibility;
  review_policy?: ReviewPolicy;
  proctoring_level?: ProctoringLevel;
  proctoring_screen_share?: boolean;
  requires_schedule?: boolean;
}
