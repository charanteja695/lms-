import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useRejectApplicantsMutation } from "@/modules/job-portal/employer/api/pipelineApi";
import { Alert, Button, Checkbox, Field, Modal, Textarea } from "@/shared/ui";

/** The only way an application is rejected: a person, a written reason, and an explicit confirmation (`confirm: true`). */
export function RejectDialog({ jobId, ids, onClose }: { jobId: string; ids: string[]; onClose: (done: boolean) => void }) {
  const notify = useNotify();
  const [reject, { isLoading }] = useRejectApplicantsMutation();
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  return (
    <Modal
      open
      onClose={() => onClose(false)}
      title={`Reject ${ids.length} applicant${ids.length === 1 ? "" : "s"}`}
      footer={
        <>
          <Button variant="secondary" onClick={() => onClose(false)} disabled={isLoading}>Cancel</Button>
          <Button
            variant="danger"
            loading={isLoading}
            disabled={!reason.trim() || !confirmed}
            onClick={async () => {
              try {
                await reject({ jobId, application_ids: ids, reason: reason.trim() }).unwrap();
                notify.success("Applicants rejected");
                onClose(true);
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Reject
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Alert tone="warning">Each candidate sees that they weren't selected. This can't be undone.</Alert>
        <Field label="Reason" required hint="Recorded with the batch for the audit trail.">{(p) => <Textarea {...p} rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
        <Checkbox label="I've reviewed these applicants myself" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
      </div>
    </Modal>
  );
}
