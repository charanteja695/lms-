import type { CertificateStatus, PdfStatus, TemplateStatus } from "@/modules/certificates/common/types";
import type { BadgeTone } from "@/shared/ui";

export const CERTIFICATE_STATUS_LABELS: Record<CertificateStatus, string> = { issued: "Issued", revoked: "Revoked" };
export const CERTIFICATE_STATUS_TONES: Record<CertificateStatus, BadgeTone> = { issued: "green", revoked: "red" };

export const PDF_STATUS_LABELS: Record<PdfStatus, string> = { pending: "Rendering", ready: "Ready", failed: "Failed" };
export const PDF_STATUS_TONES: Record<PdfStatus, BadgeTone> = { pending: "amber", ready: "green", failed: "red" };

export const TEMPLATE_STATUS_LABELS: Record<TemplateStatus, string> = { draft: "Draft", active: "Active", archived: "Archived" };
export const TEMPLATE_STATUS_TONES: Record<TemplateStatus, BadgeTone> = { draft: "gray", active: "green", archived: "red" };

/** Placeholders certificate-service accepts in body/footer text (anything else is 422 INVALID_PLACEHOLDER). */
export const TEMPLATE_PLACEHOLDERS = [
  "{student_name}", "{course_title}", "{completion_date}", "{institution_name}", "{score_percent}", "{grade}", "{issuer}", "{certificate_id}",
] as const;
