import type { Id, IsoDateTime, SortOrder } from "@/core/api/types";
import type { CertificateStatus, PdfStatus } from "@/modules/certificates/common/types";

export interface Certificate {
  certificate_id: Id;
  status: CertificateStatus;
  student_user_id: Id;
  organization_id: Id | null;
  course_id: Id;
  version_id: Id | null;
  student_name: string | null;
  course_title: string | null;
  institution_name: string | null;
  completion_date: IsoDateTime;
  score_percent: number;
  grade: string | null;
  issued_at: IsoDateTime;
  revoked_at: IsoDateTime | null;
  pdf_status: PdfStatus;
  verification_code: string;
  verification_url?: string;
  linkedin_add_url?: string;
}

/** What institution staff and exam managers additionally see (GET /certificates/{id}/details). */
export interface CertificateDetails extends Certificate {
  attempt_id: Id;
  revoke_reason: string | null;
  pdf_attempts: number;
  last_error: string | null;
}

export interface CertificateEvent {
  event_type: string;
  actor_user_id: Id | null;
  detail: Record<string, unknown> | null;
  created_at: IsoDateTime;
}

export interface CertificateFilters {
  course_id?: string;
  user_id?: string;
  status?: CertificateStatus;
  pdf_status?: PdfStatus;
  sort_order?: SortOrder;
}
