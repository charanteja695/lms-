import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { ContentStatus, ReviewAction } from "@/modules/catalog/common/types";

export interface CourseVersionSummary {
  version_id: Id;
  version_number: number;
  status: ContentStatus;
  published_at: IsoDateTime | null;
}

/** The same shape is returned for both a list row and the single-course fetch. */
export interface Course {
  course_id: Id;
  title: string;
  slug: string;
  summary: string;
  thumbnail_media_id: Id | null;
  created_by: Id;
  archived_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  versions: CourseVersionSummary[];
}

export interface CourseFilters {
  search_text?: string;
  sort_order?: SortOrder;
  include_archived?: boolean;
  published_only?: boolean;
}

export interface CourseCreateBody {
  title: string;
  slug: string;
  summary: string;
  thumbnail_media_id?: string | null;
}

export interface CourseUpdateBody {
  title?: string;
  summary?: string;
  thumbnail_media_id?: string | null;
}

/** submit/approve/reject/retire all return this — the version without its authoring tree. */
export interface CourseVersionOut {
  version_id: Id;
  version_number: number;
  status: ContentStatus;
  created_by: Id;
  submitted_at: IsoDateTime | null;
  submitted_by: Id | null;
  reviewed_at: IsoDateTime | null;
  reviewed_by: Id | null;
  reject_reason: string | null;
  published_at: IsoDateTime | null;
  retired_at: IsoDateTime | null;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

export interface Review {
  action: ReviewAction;
  actor_user_id: Id;
  comment: string | null;
  created_at: IsoDateTime;
}
