import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { CHANNEL_LABELS } from "@/modules/notifications/common/labels";
import type { Template } from "@/modules/notifications/common/types";
import { useResetTemplateMutation, useSaveTemplateMutation } from "@/modules/notifications/admin/api/notificationAdminApi";
import { Badge, Button, Field, Input, Modal, Textarea } from "@/shared/ui";

/** Edit one type's wording for one channel. Placeholders are fixed per type; the server rejects any other. */
export function TemplateDialog({ template: t, onClose }: { template: Template; onClose: () => void }) {
  const notify = useNotify();
  const [subject, setSubject] = useState(t.subject);
  const [body, setBody] = useState(t.body);
  const [save, { isLoading: saving }] = useSaveTemplateMutation();
  const [reset, { isLoading: resetting }] = useResetTemplateMutation();
  const key = { type: t.type, channel: t.channel };
  const done = (msg: string) => () => { notify.success(msg); onClose(); };

  return (
    <Modal
      open
      size="lg"
      onClose={onClose}
      title={`${t.type} · ${CHANNEL_LABELS[t.channel]}`}
      footer={
        <>
          {t.is_customised && (
            <Button variant="ghost" className="mr-auto" loading={resetting} onClick={() => void reset(key).unwrap().then(done("Reset to the default"), notify.apiError)}>
              Reset to default
            </Button>
          )}
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button loading={saving} disabled={!subject.trim() || !body.trim()} onClick={() => void save({ ...key, subject, body }).unwrap().then(done("Template saved"), notify.apiError)}>
            Save
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-1 text-xs text-slate-500">
          Placeholders: {t.variables.map((v) => <Badge key={v} tone="gray">{`\${${v}}`}</Badge>)}
        </div>
        <Field label="Subject" required>{(p) => <Input {...p} maxLength={300} value={subject} onChange={(e) => setSubject(e.target.value)} />}</Field>
        <Field label="Body" required>{(p) => <Textarea {...p} rows={8} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}
