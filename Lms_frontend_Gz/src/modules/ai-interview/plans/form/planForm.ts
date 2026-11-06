import type { Difficulty, Plan, PlanKind, Round, RoundType } from "@/modules/ai-interview/common/types";
import type { PlanBody } from "@/modules/ai-interview/plans/api/plansApi";

export interface RoundDraft {
  type: RoundType;
  minutes: string;
  questions: string;
  languages: string;
}

export interface PlanFormValues {
  title: string;
  role: string;
  skills: string;
  difficulty: Difficulty;
  duration_minutes: string;
  instructions: string;
  proctoring_level: string;
  max_attempts: string;
  retake_cooldown_days: string;
  rounds: RoundDraft[];
}

const lines = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean);
const list = (text: string) => text.split(",").map((l) => l.trim()).filter(Boolean);

export function emptyPlanForm(): PlanFormValues {
  return {
    title: "", role: "", skills: "", difficulty: "medium", duration_minutes: "30", instructions: "", proctoring_level: "none", max_attempts: "1", retake_cooldown_days: "0",
    rounds: [{ type: "intro", minutes: "5", questions: "Tell me about yourself.", languages: "" }, { type: "technical", minutes: "20", questions: "", languages: "" }],
  };
}

export function planToForm(plan: Plan): PlanFormValues {
  return {
    title: plan.title, role: plan.role, skills: plan.skills.join(", "), difficulty: plan.difficulty, duration_minutes: String(plan.duration_minutes), instructions: plan.instructions ?? "",
    proctoring_level: plan.proctoring_level, max_attempts: String(plan.max_attempts), retake_cooldown_days: String(plan.retake_cooldown_days),
    rounds: plan.rounds.map((r) => ({ type: r.type, minutes: String(r.minutes), questions: r.questions.join("\n"), languages: r.languages.join(", ") })),
  };
}

/** Criteria are left to the round type's defaults and weights to the server (it normalises them). */
export function toPlanBody(kind: PlanKind, v: PlanFormValues): PlanBody {
  const rounds: Round[] = v.rounds.map((r) => ({ type: r.type, minutes: Number(r.minutes) || 0, questions: lines(r.questions), languages: r.type === "coding" ? list(r.languages) : [], criteria: [] }));
  return {
    kind, title: v.title.trim(), role: v.role.trim(), skills: list(v.skills), difficulty: v.difficulty, duration_minutes: Number(v.duration_minutes) || 0, rounds,
    instructions: v.instructions.trim() || null, proctoring_level: v.proctoring_level, max_attempts: Number(v.max_attempts) || 1, retake_cooldown_days: Number(v.retake_cooldown_days) || 0,
  };
}
