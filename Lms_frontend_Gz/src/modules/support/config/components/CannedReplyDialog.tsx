import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import type { CannedScope } from "@/modules/support/common/types";
import { useCreateCannedReplyMutation, useUpdateCannedReplyMutation, type CannedReply } from "@/modules/support/config/api/cannedApi";
import { Button, Field, Input, Modal, Textarea } from "@/shared/ui";

/** New or edited canned reply. Managers write platform-wide ones, institution staff their institution's. */
export function CannedReplyDialog({ existing, onClose }: { existing: CannedReply | null; onClose: () => void }) {
  const notify = useNotify();
  const { isManager } = useSupportRights();
  const scope: CannedScope = existing?.scope ?? (isManager ? "platform" : "organization");
  const [title, setTitle] = useState(existing?.title ?? "");
  const [body, setBody] = useState(existing?.body ?? "");
  const [create, { isLoading: creating }] = useCreateCannedReplyMutation();
  const [update, { isLoading: updating }] = useUpdateCannedReplyMutation();

  const save = async () => {
    try {
      if (existing) await update({ cannedId: existing.canned_reply_id, title, body }).unwrap();
      else await create({ scope, title, body }).unwrap();
      notify.success(existing ? "Canned reply saved" : "Canned reply added");
      onClose();
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={existing ? "Edit canned reply" : "New canned reply"}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={creating || updating}>
            Cancel
          </Button>
          <Button loading={creating || updating} onClick={() => void save()}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {!existing && <p className="text-sm text-slate-500">{scope === "platform" ? "Available to every agent." : "Available to your institution's staff."}</p>}
        <Field label="Title" required>{(props) => <Input {...props} value={title} maxLength={120} onChange={(event) => setTitle(event.target.value)} />}</Field>
        <Field label="Body" required hint="{{student_first_name}} and {{ticket_subject}} are filled in when it's used.">
          {(props) => <Textarea {...props} rows={8} value={body} maxLength={4000} onChange={(event) => setBody(event.target.value)} />}
        </Field>
      </div>
    </Modal>
  );
}
