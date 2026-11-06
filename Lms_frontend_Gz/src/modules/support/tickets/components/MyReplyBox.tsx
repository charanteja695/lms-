import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { AttachmentPicker } from "@/modules/support/common/components/AttachmentPicker";
import { useAttachmentUploads } from "@/modules/support/common/hooks/useAttachmentUploads";
import { useReplyToMyTicketMutation } from "@/modules/support/tickets/api/myTicketsApi";
import { Button, Card, Textarea } from "@/shared/ui";

/** The student's reply, with optional files (a screenshot, a log). */
export function MyReplyBox({ ticketId }: { ticketId: string }) {
  const notify = useNotify();
  const [reply, { isLoading: sending }] = useReplyToMyTicketMutation();
  const [text, setText] = useState("");
  const uploads = useAttachmentUploads();

  const send = async () => {
    try {
      await reply({ ticketId, body: text.trim(), attachments: uploads.refs }).unwrap();
      setText("");
      uploads.reset();
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <Card title="Reply">
      <Textarea aria-label="Reply" rows={4} maxLength={8000} value={text} onChange={(event) => setText(event.target.value)} />
      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <AttachmentPicker uploads={uploads} disabled={sending} />
        <Button loading={sending} disabled={!text.trim() || uploads.uploading} onClick={() => void send()}>
          Send reply
        </Button>
      </div>
    </Card>
  );
}
