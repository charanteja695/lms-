import { cn } from "@/core/lib/cn";
import { formatDateTime } from "@/core/lib/format";
import { MessageAttachments } from "@/modules/support/common/components/MessageAttachments";
import type { TicketMessage } from "@/modules/support/common/types";
import { Badge } from "@/shared/ui";

/** A ticket's conversation. Internal notes only ever reach an agent (the student API never returns them). */
/** `ticketPath` is the API path attachments are fetched through: `/tickets/{id}` or `/agent/tickets/{id}`. */
export function MessageThread({ messages, requesterName, ticketPath }: { messages: TicketMessage[]; requesterName: string | null; ticketPath: string }) {
  if (messages.length === 0) return <p className="text-sm text-slate-500">No messages yet.</p>;
  return (
    <ol className="space-y-3">
      {messages.map((message) => {
        const fromStudent = message.author_role === "requester";
        const internal = message.kind === "internal";
        return (
          <li
            key={message.message_id}
            className={cn("rounded-lg border px-4 py-3 text-sm", internal ? "border-amber-200 bg-amber-50" : fromStudent ? "border-slate-200 bg-white" : "border-brand-100 bg-brand-50/50")}
          >
            <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="font-medium text-slate-700">{fromStudent ? (requesterName ?? "Student") : message.author_role === "system" ? "System" : "Support"}</span>
              {internal && <Badge tone="amber">Internal note</Badge>}
              <span>{formatDateTime(message.created_at)}</span>
            </div>
            <p className="whitespace-pre-wrap break-words text-slate-800">{message.body}</p>
            <MessageAttachments message={message} ticketPath={ticketPath} />
          </li>
        );
      })}
    </ol>
  );
}
