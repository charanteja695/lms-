import type { Id, IsoDateTime } from "@/core/api/types";
import type { TemplateStatus } from "@/modules/certificates/common/types";

export interface Signatory {
  name: string;
  title: string;
}

export interface GradeBand {
  min_percent: number;
  label: string;
}

export interface CertificateTemplate {
  template_id: Id;
  course_id: Id | null;
  name: string;
  status: TemplateStatus;
  title_text: string;
  body_text: string;
  footer_text: string | null;
  accent_color: string;
  signatories: Signatory[];
  grade_bands: GradeBand[];
  created_by: Id;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  activated_at: IsoDateTime | null;
}

export interface TemplateCreateBody {
  name: string;
  course_id: Id | null;
  title_text: string;
  body_text: string | null;
  footer_text: string | null;
  accent_color: string | null;
  signatories: Signatory[];
  grade_bands: GradeBand[] | null;
}

export type TemplateUpdateBody = Partial<Omit<TemplateCreateBody, "course_id">>;

export interface TemplateFilters {
  course_id?: string;
  status?: TemplateStatus;
}
