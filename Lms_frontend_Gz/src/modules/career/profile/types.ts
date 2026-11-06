import type { ItemKind } from "@/modules/career/common/types";

export interface ProfileLink {
  label: string;
  url: string;
}

export interface CareerProfileFields {
  headline: string | null;
  summary: string | null;
  phone: string | null;
  location: string | null;
  links: ProfileLink[];
  target_roles: string[];
  revision: number;
}

export interface ProfileItem {
  item_id: string;
  kind: ItemKind;
  verified: boolean;
  label: string;
  source: string;
  active: boolean;
  data: Record<string, unknown>;
  derived: { course_title?: string; percentile?: number | null; cohort_size?: number };
  position: number;
  inactive_reason: string | null;
}

export interface CareerProfile {
  profile: CareerProfileFields;
  personal: { name: string; email: string | null; name_verified: boolean };
  items: ProfileItem[];
}

export type ProfileUpdateBody = Partial<Omit<CareerProfileFields, "revision">>;

/** What career-service read from an uploaded resume: checked entries to pick from (nothing is saved yet). */
export interface ImportResult {
  message: string;
  profile: { headline: string | null; summary: string | null; phone: string | null; location: string | null };
  items: { kind: ItemKind; data: Record<string, unknown>; label: string }[];
  skipped: number;
}
