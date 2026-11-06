import { useParams } from "react-router-dom";

import { useGetCertificateQuery } from "@/modules/certificates/issued/api/certificatesApi";
import { CertificateActions } from "@/modules/certificates/issued/components/detail/CertificateActions";
import { CertificateStaffCards } from "@/modules/certificates/issued/components/detail/CertificateStaffCards";
import { CertificateSummaryCard } from "@/modules/certificates/issued/components/detail/CertificateSummaryCard";
import { Alert, EmptyState, PageHeader, PageLoader } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export function CertificateDetailPage() {
  const { can, holds } = useCan();
  const { certificateId = "" } = useParams();
  const { data: certificate, isLoading, isError } = useGetCertificateQuery(certificateId, { skip: !certificateId });
  const isStudent = holds("certificates.own");
  const canManage = can("exams.manage");

  if (isLoading) return <PageLoader />;
  if (isError || !certificate) return <EmptyState icon="alert" title="Certificate not found" />;

  return (
    <>
      <PageHeader
        title={certificate.course_title ?? "Certificate"}
        description={certificate.student_name ?? undefined}
        backTo="/certificates/issued"
        backLabel="Certificates"
        actions={<CertificateActions certificate={certificate} canManage={canManage} />}
      />
      <div className="space-y-4">
        {certificate.status === "revoked" && <Alert tone="error" title="This certificate has been revoked" />}
        {certificate.pdf_status === "pending" && <Alert tone="info" title="The PDF is still rendering">Check back in a minute.</Alert>}
        <CertificateSummaryCard certificate={certificate} />
        {!isStudent && <CertificateStaffCards certificateId={certificate.certificate_id} />}
      </div>
    </>
  );
}
