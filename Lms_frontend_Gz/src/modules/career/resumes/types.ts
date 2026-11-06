import type { ResumeDocument, SectionKey } from "@/modules/career/common/types";

export interface Resume {
  resume_id: string;
  title: string;
  target_role: string | null;
  template_key: string;
  experience_level: string;
  draft_revision: number;
  latest_version_no: number;
  shared: boolean;
  share_expires_at: string | null;
  /** Only in lists: the live score. The detail carries the whole report. */
  ats_score?: number | null;
  created_at: string;
  updated_at: string;
}

export interface DraftSection {
  key: SectionKey;
  title?: string | null;
  visible: boolean;
  items: { item_id: string; bullets?: string[] | null }[];
}

export interface Draft {
  summary: { text?: string | null; visible: boolean };
  personal: { show_phone: boolean; show_location: boolean; show_links: boolean };
  sections: DraftSection[];
}

export interface AtsResult {
  score: number;
  word_count: number;
  components: { key: string; label: string; points: number; max: number; detail: string }[];
  fixes: { code: string; severity: "high" | "medium" | "low"; message: string; section: string | null; item_id: string | null }[];
  keywords: { term: string; weight: number; present: boolean }[];
  /** Parts short of full marks, biggest gain first; `fix_codes` are the fixes that earn the points. */
  path_to_100: { key: string; label: string; gain: number; fix_codes: string[] }[];
}

export interface ResumeDetail {
  resume: Resume;
  job_description: string | null;
  draft: Draft;
  document: ResumeDocument;
  ats: AtsResult;
}

export interface ResumeCreateBody {
  title: string;
  target_role?: string | null;
  template_key?: string | null;
  job_description?: string | null;
  experience_level?: string;
  blank?: boolean;
}

export interface ResumeUpdateBody {
  expected_revision: number;
  title?: string;
  target_role?: string | null;
  template_key?: string;
  job_description?: string | null;
  experience_level?: string;
  draft?: Draft;
}

export interface ResumeTemplate {
  key: string;
  name: string;
  description: string;
  ats_safe: boolean;
}

export interface ResumeVersion {
  version_no: number;
  label: string | null;
  source: string;
  template_key: string;
  ats_score: number | null;
  note: string | null;
  created_at: string;
}

/** A choice the server offers (levels, tones): `note` explains what picking it changes. */
export interface Option {
  key: string;
  label: string;
  note: string;
}

export interface StartOption {
  key: string;
  label: string;
  description: string;
  /** File types this start reads; empty = no file. */
  accepts: string[];
}

export interface ResumeOptions {
  experience_levels: Option[];
  start_options: StartOption[];
  role_suggestions: string[];
  ai_tones: Option[];
  max_resumes: number;
  max_import_bytes: number;
  share_expiry_days: number[];
  share_default_days: number;
}
