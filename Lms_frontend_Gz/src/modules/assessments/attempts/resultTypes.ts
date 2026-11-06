import type { Id, IsoDateTime } from "@/core/api/types";
import type { AttemptResult, AttemptStatus, IntegrityStatus, QuestionType } from "@/modules/assessments/common/types";

export interface ReviewQuestion {
  question_id: Id;
  position: number;
  question_type: QuestionType;
  text: string;
  body: Record<string, unknown>;
  marks: number;
  marks_awarded: number | null;
  is_correct: boolean | null;
  grading_status: string | null;
  feedback: string | null;
  rubric_scores: Record<string, unknown> | null;
  response: Record<string, unknown> | null;
  answer_key: Record<string, unknown> | null;
  explanation: string | null;
}

export interface AttemptResultView {
  attempt_id: Id;
  test_id: Id;
  test_title: string;
  status: AttemptStatus;
  released: boolean;
  message: string | null;
  result: AttemptResult | null;
  score: number | null;
  max_score: number | null;
  percent: number | null;
  pass_mark_percent: number | null;
  integrity_status: IntegrityStatus | null;
  submitted_at: IsoDateTime | null;
  released_at: IsoDateTime | null;
  questions: ReviewQuestion[] | null;
}
