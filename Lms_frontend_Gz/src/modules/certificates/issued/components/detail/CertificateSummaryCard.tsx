import { formatDate, formatDateTime } from "@/core/lib/format";
import { CertificateStatusBadge, PdfStatusBadge } from "@/modules/certificates/common/components/StatusBadges";
import type { Certificate } from "@/modules/certificates/issued/types";
import { Card, DescriptionList } from "@/shared/ui";

export function CertificateSummaryCard({ certificate }: { certificate: Certificate }) {
  return (
    <Card title="Certificate">
      <DescriptionList
        items={[
          { label: "Student", value: certificate.student_name },
          { label: "Course", value: certificate.course_title },
          { label: "Institution", value: certificate.institution_name },
          { label: "Completed", value: formatDate(certificate.completion_date) },
          { label: "Score", value: `${certificate.score_percent.toFixed(1)}%` },
          { label: "Grade", value: certificate.grade },
          { label: "Status", value: <CertificateStatusBadge status={certificate.status} /> },
          { label: "PDF", value: <PdfStatusBadge status={certificate.pdf_status} /> },
          { label: "Issued", value: formatDateTime(certificate.issued_at) },
          { label: "Revoked", value: certificate.revoked_at ? formatDateTime(certificate.revoked_at) : null },
          { label: "Verification code", value: <span className="font-mono">{certificate.verification_code}</span>, span: 2 },
        ]}
      />
    </Card>
  );
}
