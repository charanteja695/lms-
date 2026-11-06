import { useParams } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { toApiError } from "@/core/lib/apiError";
import { useVerifyCertificateQuery } from "@/modules/certificates/verification/api/verifyApi";
import { Alert, Card, DescriptionList, PageLoader } from "@/shared/ui";

/** The page a certificate's QR code opens. The server decides validity; this only shows its answer. */
export function VerifyCertificatePage() {
  const { code = "" } = useParams();
  const { data, isLoading, error } = useVerifyCertificateQuery(code, { skip: !code });

  if (isLoading) return <PageLoader />;
  if (error || !data) {
    const apiError = error ? toApiError(error) : null;
    return (
      <Alert tone="error" title="Certificate not found">
        {apiError?.message ?? "No certificate matches this code. Check the link or QR code and try again."}
      </Alert>
    );
  }

  const { verification } = data;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-900">Certificate verification</h1>
      <Alert tone={verification.valid ? "success" : "error"} title={data.message}>
        {!verification.valid && verification.revoked_at && `Revoked on ${formatDate(verification.revoked_at)}.`}
      </Alert>
      <Card>
        <DescriptionList
          columns={1}
          items={[
            { label: "Awarded to", value: verification.student_name },
            { label: "Course", value: verification.course_title },
            { label: "Institution", value: verification.institution_name },
            { label: "Completed", value: formatDate(verification.completion_date) },
            { label: "Grade", value: verification.grade ? `${verification.grade} (${verification.score_percent.toFixed(1)}%)` : `${verification.score_percent.toFixed(1)}%` },
            { label: "Issued by", value: `${verification.issuer} on ${formatDate(verification.issued_at)}` },
            { label: "Certificate ID", value: <span className="font-mono">{verification.certificate_id}</span> },
          ]}
        />
      </Card>
    </div>
  );
}
