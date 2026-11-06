import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useListCannedRepliesQuery, useRenderCannedReplyMutation } from "@/modules/support/config/api/cannedApi";
import { useAgentReplyMutation } from "@/modules/support/agent/api/agentTicketsApi";
import { AttachmentPicker } from "@/modules/support/common/components/AttachmentPicker";
import { useAttachmentUploads } from "@/modules/support/common/hooks/useAttachmentUploads";
import { Button, Card, Checkbox, Select, Textarea } from "@/shared/ui";

type Then = "" | "waiting_on_student" | "resolved";
const THEN_OPTIONS = [
  { value: "waiting_on_student", label: "…and wait on the student" },
  { value: "resolved", label: "…and mark resolved" },
];

/** Reply to the student, or leave an internal note. A canned reply is filled in server-side for this ticket, then editable. */
export function AgentReplyBox({ ticketId }: { ticketId: string }) {
  const notify = useNotify();
  const { data: canned = [] } = useListCannedRepliesQuery({});
  const [render] = useRenderCannedReplyMutation();
  const [reply, { isLoading }] = useAgentReplyMutation();
  const [text, setText] = useState("");
  const [internal, setInternal] = useState(false);
  const [then, setThen] = useState<Then>("");
  const [cannedId, setCannedId] = useState<string | null>(null);
  const uploads = useAttachmentUploads();

  const insertCanned = async (id: string) => {
    if (!id) return;
    try {
      setText(await render({ cannedId: id, ticketId }).unwrap());
      setCannedId(id);
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Card title={internal ? "Internal note" : "Reply"}>
      <div className="space-y-3">
        {canned.length > 0 && !internal && (
          <Select aria-label="Insert a canned reply" value="" placeholder="Insert a canned reply…" options={canned.map((item) => ({ value: item.canned_reply_id, label: item.title }))} onChange={(event) => void insertCanned(event.target.value)} />
        )}
        <Textarea
          aria-label={internal ? "Internal note" : "Reply"}
          rows={5}
          maxLength={8000}
          value={text}
          className={internal ? "bg-amber-50" : undefined}
          onChange={(event) => setText(event.target.value)}
        />
        <AttachmentPicker uploads={uploads} disabled={isLoading} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Checkbox label="Internal note (the student never sees it)" checked={internal} onChange={(event) => setInternal(event.target.checked)} />
          <div className="flex items-center gap-2">
            {!internal && <Select aria-label="Then" className="w-56" value={then} placeholder="…and keep it open" options={THEN_OPTIONS} onChange={(event) => setThen(event.target.value as Then)} />}
            <Button
              loading={isLoading}
              disabled={!text.trim() || uploads.uploading}
              onClick={async () => {
                try {
                  await reply({ ticketId, body: { body: text.trim(), internal, then: !internal && then ? then : null, canned_reply_id: cannedId, attachments: uploads.refs } }).unwrap();
                  uploads.reset();
                  setText("");
                  setThen("");
                  setCannedId(null);
                } catch (error) {
                  notify.apiError(error);
                }
              }}
            >
              {internal ? "Add note" : "Send"}
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
