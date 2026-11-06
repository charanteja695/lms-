import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetCertificateDownloadMutation, useRegenerateCertificatePdfMutation } from "@/modules/certificates/issued/api/certificatesApi";
import { RevokeCertificateDialog } from "@/modules/certificates/issued/components/detail/RevokeCertificateDialog";
import type { Certificate } from "@/modules/certificates/issued/types";
import { Button } from "@/shared/ui";

export function CertificateActions({ certificate, canManage }: { certificate: Certificate; canManage: boolean }) {
  const notify = useNotify();
  const [getDownload, { isLoading: downloading }] = useGetCertificateDownloadMutation();
  const [regenerate, { isLoading: regenerating }] = useRegenerateCertificatePdfMutation();
  const [revoking, setRevoking] = useState(false);
  const issued = certificate.status === "issued";
  const { user } = useAuth();
  const { acts } = useCan();
  // their own certificate: downloading and sharing is the My certificates page's Export cell
  const mayShare = certificate.student_user_id !== user?.user_id || acts("my_certificates.export", "certificates.own");

  const download = async () => {
    try {
      const { url } = await getDownload(certificate.certificate_id).unwrap();
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (error) {
      notify.apiError(error);
    }
  };

  const copyLink = async () => {
    if (!certificate.verification_url) return;
    try {
      await navigator.clipboard.writeText(certificate.verification_url);
      notify.success("Verification link copied");
    } catch {
      notify.error("Could not copy", certificate.verification_url);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {mayShare && <Button icon="download" loading={downloading} disabled={certificate.pdf_status !== "ready"} onClick={() => void download()}>
        Download PDF
      </Button>}
      {issued && mayShare && certificate.verification_url && (
        <Button variant="secondary" icon="key" onClick={() => void copyLink()}>
          Copy verification link
        </Button>
      )}
      {issued && certificate.linkedin_add_url && (
        <Button variant="secondary" icon="briefcase" onClick={() => window.open(certificate.linkedin_add_url, "_blank", "noopener,noreferrer")}>
          Add to LinkedIn
        </Button>
      )}
      {canManage && (
        <Button
          variant="secondary"
          icon="refresh"
          loading={regenerating}
          onClick={async () => {
            try {
              await regenerate(certificate.certificate_id).unwrap();
              notify.success("PDF re-render requested");
            } catch (error) {
              notify.apiError(error);
            }
          }}
        >
          Regenerate PDF
        </Button>
      )}
      {canManage && issued && (
        <Button variant="danger" icon="ban" onClick={() => setRevoking(true)}>
          Revoke
        </Button>
      )}
      <RevokeCertificateDialog open={revoking} onClose={() => setRevoking(false)} certificateId={certificate.certificate_id} />
    </div>
  );
}
