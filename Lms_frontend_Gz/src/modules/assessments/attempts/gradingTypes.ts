import type { Id, IsoDateTime } from "@/core/api/types";
import type { QuestionType } from "@/modules/assessments/common/types";

export interface GradingQueueItem {
  attempt_id: Id;
  test_id: Id;
  user_id: Id;
  question_id: Id;
  question_type: QuestionType;
  text: string;
  marks: number;
  rubric: Record<string, unknown>[];
  response: Record<string, unknown> | null;
  submitted_at: IsoDateTime | null;
}

export interface GradeBody {
  marks?: number | null;
  rubric_scores?: Record<string, number> | null;
  feedback?: string | null;
}
