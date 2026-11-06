import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { EnrollmentStatus, ItemType } from "@/modules/learning/common/types";

export interface Enrollment {
  enrollment_id: Id;
  batch_id: Id;
  student_user_id: Id;
  status: EnrollmentStatus;
  enrolled_at: IsoDateTime;
  withdrawn_at: IsoDateTime | null;
}

export interface EnrollmentFilters {
  status?: EnrollmentStatus;
  sort_order?: SortOrder;
  batch_id?: string;
}

export interface EnrollmentCreateBody {
  student_user_id: string;
}

export interface ItemUnlock {
  topic_item_id: Id;
  title: string;
  item_type: ItemType;
  position: number;
  required: boolean;
  completed: boolean;
}

export interface TopicUnlock {
  topic_id: Id;
  title: string;
  position: number;
  unlocked: boolean;
  completed: boolean;
  completed_items: number;
  required_items: number;
  test_required: boolean;
  test_passed: boolean;
  items: ItemUnlock[];
}

export interface ModuleUnlock {
  module_id: Id;
  title: string;
  position: number;
  unlocked: boolean;
  completed: boolean;
  test_required: boolean;
  test_passed: boolean;
  topics: TopicUnlock[];
}

export interface UnlockState {
  modules: ModuleUnlock[];
  eligible_for_final: boolean;
}
