import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { Bloom, QuestionStatus, QuestionType, VersionStatus } from "@/modules/assessments/common/types";

export interface QuestionVersion {
  version_no: number;
  status: VersionStatus;
  text: string;
  body: Record<string, unknown>;
  answer_key: Record<string, unknown>;
  explanation: string | null;
  default_marks: number;
  difficulty: number;
  bloom: Bloom | null;
  skills: string[];
  topics: string[];
  tags: string[];
  review_note: string | null;
  created_by: Id;
  created_at: IsoDateTime;
  submitted_at: IsoDateTime | null;
  reviewed_by: Id | null;
  reviewed_at: IsoDateTime | null;
  published_at: IsoDateTime | null;
}

export interface QuestionStats {
  sample_size: number;
  difficulty_index: number | null;
  discrimination: number | null;
  computed_at: IsoDateTime;
}

export interface Question {
  question_id: Id;
  question_type: QuestionType;
  status: QuestionStatus;
  organization_id: Id | null;
  current_version_no: number | null;
  latest_version_no: number;
  created_by: Id;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  /** The live, published version students see, if any. */
  current: QuestionVersion | null;
  /** The editable draft/in-review version, if any. */
  working: QuestionVersion | null;
  stats: QuestionStats | null;
}

export interface QuestionListItem {
  question_id: Id;
  question_type: QuestionType;
  status: QuestionStatus;
  current_version_no: number | null;
  latest_version_no: number;
  latest_version_status: VersionStatus;
  text: string;
  difficulty: number;
  bloom: Bloom | null;
  default_marks: number;
  skills: string[];
  topics: string[];
  tags: string[];
  created_at: IsoDateTime;
}

export interface QuestionFilters {
  question_type?: QuestionType;
  status?: QuestionStatus;
  version_status?: VersionStatus;
  difficulty_min?: number;
  difficulty_max?: number;
  bloom?: Bloom;
  skill?: string;
  topic?: string;
  tag?: string;
  search?: string;
  sort_order?: SortOrder;
}

export interface QuestionCreateBody {
  question_type: QuestionType;
  text: string;
  body?: Record<string, unknown>;
  answer_key?: Record<string, unknown>;
  explanation?: string | null;
  default_marks?: number;
  difficulty?: number;
  bloom?: Bloom | null;
  skills?: string[];
  topics?: string[];
  tags?: string[];
}

export interface QuestionUpdateBody {
  text?: string;
  body?: Record<string, unknown>;
  answer_key?: Record<string, unknown>;
  explanation?: string | null;
  default_marks?: number;
  difficulty?: number;
  bloom?: Bloom | null;
  skills?: string[];
  topics?: string[];
  tags?: string[];
}
