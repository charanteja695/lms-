import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { CourseRequestStatus } from "@/modules/subscriptions/common/types";

export interface CourseRequest {
  course_request_id: Id;
  organization_id: Id;
  course_id: Id;
  requested_seats: number;
  requested_term_days: number;
  status: CourseRequestStatus;
  requested_by: Id;
  decided_by: Id | null;
  decided_at: IsoDateTime | null;
  decision_reason: string | null;
  created_at: IsoDateTime;
  course_name?: string | null;
  institution_name?: string | null;
  requester_name?: string | null;
}

export interface CourseRequestFilters {
  status?: CourseRequestStatus;
  sort_order?: SortOrder;
}

export interface CourseRequestCreateBody {
  course_id: string;
  requested_seats?: number;
  requested_term_days?: number;
}

export interface ApproveRequestBody {
  seats?: number | null;
  term_days?: number | null;
}
