import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useMakeOfferMutation } from "@/modules/job-portal/employer/api/pipelineApi";
import { Button, Field, Input, Modal, Textarea } from "@/shared/ui";

export function OfferDialog({ applicationId, defaultTitle, currency, onClose }: { applicationId: string; defaultTitle: string; currency: string; onClose: () => void }) {
  const notify = useNotify();
  const [offer, { isLoading }] = useMakeOfferMutation();
  const [ctc, setCtc] = useState("");
  const [title, setTitle] = useState(defaultTitle);
  const [joining, setJoining] = useState("");
  const [validDays, setValidDays] = useState("7");
  const [note, setNote] = useState("");
  const unit = currency === "INR" ? 100_000 : 1000;

  return (
    <Modal
      open
      onClose={onClose}
      title="Make an offer"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>Cancel</Button>
          <Button
            loading={isLoading}
            disabled={!ctc}
            onClick={async () => {
              try {
                await offer({ id: applicationId, ctc: Math.round(Number(ctc) * unit), currency, role_title: title || undefined, joining_date: joining || undefined, valid_days: Number(validDays) || undefined, note: note || undefined }).unwrap();
                notify.success("Offer sent");
                onClose();
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Send offer
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={`CTC (${currency === "INR" ? "lakhs" : "thousands"} per year)`} required>{(p) => <Input {...p} type="number" min={0} step="0.5" value={ctc} onChange={(e) => setCtc(e.target.value)} />}</Field>
        <Field label="Role title">{(p) => <Input {...p} maxLength={160} value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
        <Field label="Joining date">{(p) => <Input {...p} type="date" value={joining} onChange={(e) => setJoining(e.target.value)} />}</Field>
        <Field label="Valid for (days)">{(p) => <Input {...p} type="number" min={1} max={60} value={validDays} onChange={(e) => setValidDays(e.target.value)} />}</Field>
        <Field label="Note" className="sm:col-span-2">{(p) => <Textarea {...p} rows={3} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
