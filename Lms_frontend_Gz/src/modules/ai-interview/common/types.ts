/** Mirrors ai-interview-service's enums and shapes (see docs/API.md). */
export type PlanKind = "mock" | "screening";
export type PlanStatus = "draft" | "published" | "retired";
export type Difficulty = "easy" | "medium" | "hard" | "senior";
export type RoundType = "intro" | "technical" | "coding" | "system_design" | "behavioural";
export type InterviewStatus = "invited" | "in_progress" | "completed" | "evaluated" | "reviewed" | "expired" | "cancelled";
export type Recommendation = "strong_yes" | "yes" | "lean_no" | "no";

export interface Round {
  type: RoundType;
  minutes: number;
  questions: string[];
  languages: string[];
  criteria: string[];
}

export interface Plan {
  plan_id: string;
  family_id: string;
  version: number;
  owner_org_id: string | null;
  kind: PlanKind;
  title: string;
  role: string;
  skills: string[];
  difficulty: Difficulty;
  duration_minutes: number;
  rounds: Round[];
  criteria_weights: Record<string, number>;
  instructions: string | null;
  proctoring_level: string;
  max_attempts: number;
  retake_cooldown_days: number;
  status: PlanStatus;
  published_at: string | null;
  created_at: string;
}

export interface Interview {
  interview_id: string;
  plan_id: string;
  kind: PlanKind;
  status: InterviewStatus;
  attempt_no: number;
  role: string;
  duration_minutes: number;
  invite_expires_at: string | null;
  started_at: string | null;
  ends_at: string | null;
  completed_at: string | null;
  round_index: number;
  turn_count: number;
  code_runs: number;
  feedback_released: boolean;
  retake_granted: boolean;
  created_at: string;
  current_round?: { key: string; type: RoundType; minutes: number; languages: string[]; number: number; total: number } | null;
  /** In my own list: the overall score once feedback is released (1 to `score_max`). */
  overall_score?: number | null;
  score_max?: number;
}

export interface Turn {
  seq: number;
  round: string;
  speaker: "interviewer" | "candidate" | "system";
  kind: "question" | "follow_up" | "answer" | "code" | "code_result" | "note";
  text: string;
  elapsed_ms: number;
  via: string;
  meta: Record<string, unknown> | null;
}

export interface Appeal {
  appeal_id: string;
  interview_id: string;
  user_id: string;
  reason: string;
  status: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  created_at: string;
}
