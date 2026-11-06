import type { Difficulty, InterviewStatus, PlanStatus, Recommendation, RoundType } from "@/modules/ai-interview/common/types";
import type { BadgeTone } from "@/shared/ui";

export const ROUND_LABELS: Record<RoundType, string> = { intro: "Introduction", technical: "Technical", coding: "Live coding", system_design: "System design", behavioural: "Behavioural" };
export const DIFFICULTY_LABELS: Record<Difficulty, string> = { easy: "Easy", medium: "Medium", hard: "Hard", senior: "Senior" };

export const PLAN_STATUS_LABELS: Record<PlanStatus, string> = { draft: "Draft", published: "Published", retired: "Retired" };
export const PLAN_STATUS_TONES: Record<PlanStatus, BadgeTone> = { draft: "gray", published: "green", retired: "red" };

export const INTERVIEW_STATUS_LABELS: Record<InterviewStatus, string> = {
  invited: "Invited", in_progress: "In progress", completed: "Completed", evaluated: "Evaluated", reviewed: "Reviewed", expired: "Expired", cancelled: "Cancelled",
};
export const INTERVIEW_STATUS_TONES: Record<InterviewStatus, BadgeTone> = {
  invited: "blue", in_progress: "amber", completed: "indigo", evaluated: "purple", reviewed: "green", expired: "gray", cancelled: "gray",
};

export const RECOMMENDATION_LABELS: Record<Recommendation, string> = { strong_yes: "Strong yes", yes: "Yes", lean_no: "Lean no", no: "No" };
export const RECOMMENDATION_TONES: Record<Recommendation, BadgeTone> = { strong_yes: "green", yes: "green", lean_no: "amber", no: "red" };
