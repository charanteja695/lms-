import {
  INTERVIEW_STATUS_LABELS, INTERVIEW_STATUS_TONES, PLAN_STATUS_LABELS, PLAN_STATUS_TONES, RECOMMENDATION_LABELS, RECOMMENDATION_TONES,
} from "@/modules/ai-interview/common/labels";
import type { InterviewStatus, PlanStatus, Recommendation } from "@/modules/ai-interview/common/types";
import { Badge } from "@/shared/ui";

export const PlanStatusBadge = ({ status }: { status: PlanStatus }) => <Badge tone={PLAN_STATUS_TONES[status]}>{PLAN_STATUS_LABELS[status]}</Badge>;
export const InterviewStatusBadge = ({ status }: { status: InterviewStatus }) => <Badge tone={INTERVIEW_STATUS_TONES[status] ?? "gray"}>{INTERVIEW_STATUS_LABELS[status] ?? status}</Badge>;
export function RecommendationBadge({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  const known = value as Recommendation;
  return <Badge tone={RECOMMENDATION_TONES[known] ?? "gray"}>{RECOMMENDATION_LABELS[known] ?? value}</Badge>;
}
