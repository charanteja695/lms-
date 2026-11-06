import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { BatchStatus } from "@/modules/learning/common/types";

export interface Batch {
  batch_id: Id;
  organization_id: Id;
  version_id: Id;
  course_id: Id;
  /** The course's title. Display only, mirrored from catalog-service. */
  title: string;
  subscription_id: Id;
  name: string;
  status: BatchStatus;
  created_by: Id;
  created_at: IsoDateTime;
}

export interface BatchFilters {
  status?: BatchStatus;
  sort_order?: SortOrder;
}

export interface BatchCreateBody {
  course_id: string;
  name: string;
  organization_id?: string | null;
}
