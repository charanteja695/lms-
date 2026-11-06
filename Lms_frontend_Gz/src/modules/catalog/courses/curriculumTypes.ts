import type { Id, IsoDateTime } from "@/core/api/types";
import type { ContentStatus, ItemType, UnlockMode } from "@/modules/catalog/common/types";

export interface CourseRule {
  unlock_mode: UnlockMode;
  final_test_id: Id | null;
  final_pass_mark: number;
  final_test_attempts: number;
  final_test_cooldown_days: number;
}

export interface CourseRuleUpdateBody {
  unlock_mode?: UnlockMode;
  final_test_id?: string | null;
  final_pass_mark?: number;
  final_test_attempts?: number;
  final_test_cooldown_days?: number;
}

export interface TopicItem {
  topic_item_id: Id;
  item_type: ItemType;
  title: string;
  description?: string;
  position: number;
  required: boolean;
  media_id: Id | null;
  media_ready: boolean;
  transcript_ready: boolean;
  duration_seconds: number | null;
  content_text: string | null;
}

export interface TopicItemCreateBody {
  item_type: ItemType;
  title: string;
  required?: boolean;
  media_id?: string | null;
  content_text?: string | null;
}

export interface TopicItemUpdateBody {
  title?: string;
  required?: boolean;
  media_id?: string | null;
  content_text?: string | null;
}

export interface TopicDetail {
  topic_id: Id;
  title: string;
  description?: string;
  position: number;
  pass_mark: number;
  topic_test_id: Id | null;
  items: TopicItem[];
}

export interface TopicCreateBody {
  title: string;
  pass_mark?: number;
}

export interface TopicUpdateBody {
  title?: string;
  pass_mark?: number;
  topic_test_id?: string | null;
}

export interface ModuleDetail {
  module_id: Id;
  title: string;
  description?: string;
  position: number;
  pass_mark: number;
  module_test_id: Id | null;
  topics: TopicDetail[];
}

export interface ModuleCreateBody {
  title: string;
  pass_mark?: number;
}

export interface ModuleUpdateBody {
  title?: string;
  pass_mark?: number;
  module_test_id?: string | null;
}

export interface CourseVersionDetail {
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
  rule: CourseRule;
  modules: ModuleDetail[];
}
