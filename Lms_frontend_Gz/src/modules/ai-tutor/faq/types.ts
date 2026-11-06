import type { Id, IsoDateTime } from "@/core/api/types";
import type { FaqScope, FaqStatus } from "@/modules/ai-tutor/common/types";

export interface FaqEntry {
  faq_id: Id;
  scope: FaqScope;
  organization_id: Id | null;
  course_id: Id | null;
  question: string;
  answer: string;
  status: FaqStatus;
  helpful_count: number;
  created_at: IsoDateTime;
}

export interface FaqManageFilters {
  status?: FaqStatus;
  scope?: FaqScope;
  course_id?: string;
}

export interface FaqCreateBody {
  scope: FaqScope;
  organization_id: Id | null;
  course_id: Id | null;
  question: string;
  answer: string;
}
