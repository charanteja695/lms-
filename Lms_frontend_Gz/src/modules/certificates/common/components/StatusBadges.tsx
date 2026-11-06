import {
  CERTIFICATE_STATUS_LABELS, CERTIFICATE_STATUS_TONES, PDF_STATUS_LABELS, PDF_STATUS_TONES, TEMPLATE_STATUS_LABELS, TEMPLATE_STATUS_TONES,
} from "@/modules/certificates/common/labels";
import type { CertificateStatus, PdfStatus, TemplateStatus } from "@/modules/certificates/common/types";
import { Badge } from "@/shared/ui";

export function CertificateStatusBadge({ status }: { status: CertificateStatus }) {
  return <Badge tone={CERTIFICATE_STATUS_TONES[status]}>{CERTIFICATE_STATUS_LABELS[status]}</Badge>;
}

export function PdfStatusBadge({ status }: { status: PdfStatus }) {
  return <Badge tone={PDF_STATUS_TONES[status]}>PDF: {PDF_STATUS_LABELS[status]}</Badge>;
}

export function TemplateStatusBadge({ status }: { status: TemplateStatus }) {
  return <Badge tone={TEMPLATE_STATUS_TONES[status]}>{TEMPLATE_STATUS_LABELS[status]}</Badge>;
}
