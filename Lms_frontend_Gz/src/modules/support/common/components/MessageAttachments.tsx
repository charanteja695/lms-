import { useNotify } from "@/core/hooks/useNotify";
import { formatBytes } from "@/core/lib/format";
import { useGetAttachmentLinkMutation } from "@/modules/support/common/api/attachmentsApi";
import type { TicketMessage } from "@/modules/support/common/types";
import { Icon } from "@/shared/ui";

/** A message's files. Each click asks for a fresh short-lived link and opens it in a new tab. */
export function MessageAttachments({ message, ticketPath }: { message: TicketMessage; ticketPath: string }) {
  const notify = useNotify();
  const [getLink] = useGetAttachmentLinkMutation();
  if (!message.attachments?.length) return null;

  const open = async (index: number) => {
    const tab = window.open("", "_blank"); // opened during the click, so pop-up blockers allow it
    try {
      const { url } = await getLink({ ticketPath, messageId: message.message_id, index }).unwrap();
      if (tab) tab.location.href = url;
      else window.location.assign(url);
    } catch (error) {
      tab?.close();
      notify.apiError(error);
    }
  };

  return (
    <ul className="mt-2 flex flex-wrap gap-2">
      {message.attachments.map((file, index) => (
        <li key={`${message.message_id}-${index}`} className="max-w-full">
          <button
            type="button"
            onClick={() => void open(index)}
            className="flex max-w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 hover:border-brand-300 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40"
          >
            <Icon name="paperclip" size={14} className="shrink-0 text-slate-400" />
            <span className="truncate">{file.filename}</span>
            <span className="shrink-0 text-slate-400">{formatBytes(file.size_bytes)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
