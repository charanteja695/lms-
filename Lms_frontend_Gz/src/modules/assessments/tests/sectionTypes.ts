import type { Id } from "@/core/api/types";
import type { Bloom, QuestionType, SlotType } from "@/modules/assessments/common/types";

export interface PoolCriteria {
  types?: QuestionType[];
  difficulty_min?: number;
  difficulty_max?: number;
  bloom?: Bloom[];
  skills?: string[];
  topics?: string[];
  tags?: string[];
}

export interface Slot {
  position: number;
  slot_type: SlotType;
  question_id: Id | null;
  criteria: PoolCriteria | null;
  count: number;
  marks: number;
}

export interface SlotInput {
  slot_type: SlotType;
  question_id?: string | null;
  criteria?: PoolCriteria | null;
  count?: number;
  marks?: number | null;
}

export interface Section {
  section_id: Id;
  position: number;
  title: string;
  instructions: string | null;
  time_limit_minutes: number | null;
  slots: Slot[];
}

export interface SectionInput {
  title: string;
  instructions?: string | null;
  time_limit_minutes?: number | null;
  slots: SlotInput[];
}
