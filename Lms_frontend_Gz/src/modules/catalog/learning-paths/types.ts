import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { ContentStatus } from "@/modules/catalog/common/types";

export interface LearningPathItem {
  course_id: Id;
  position: number;
  title: string;
  slug: string;
}

export interface LearningPath {
  learning_path_id: Id;
  title: string;
  slug: string;
  description: string;
  /** Learning paths only ever move draft -> published -> archived (no review step). */
  status: ContentStatus;
  created_by: Id;
  published_at: IsoDateTime | null;
  archived_at: IsoDateTime | null;
  items: LearningPathItem[];
}

export interface LearningPathFilters {
  search_text?: string;
  sort_order?: SortOrder;
}

export interface LearningPathCreateBody {
  title: string;
  slug: string;
  description: string;
}

export interface LearningPathUpdateBody {
  title?: string;
  description?: string;
}
