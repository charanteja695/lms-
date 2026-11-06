import { useRef } from "react";

import { formatBytes } from "@/core/lib/format";
import type { useAttachmentUploads } from "@/modules/support/common/hooks/useAttachmentUploads";
import { Button, Icon, Spinner } from "@/shared/ui";

/** "Attach files" plus the picked files, each uploading on its own. Allowed types and sizes are checked by the server. */
export function AttachmentPicker({ uploads, disabled }: { uploads: ReturnType<typeof useAttachmentUploads>; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-2">
      <input
        ref={input}
        type="file"
        multiple
        hidden
        onChange={(event) => {
          uploads.add(event.target.files);
          event.target.value = ""; // picking the same file again still triggers a change
        }}
      />
      {uploads.items.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {uploads.items.map((item) => (
            <li key={item.id} className="flex max-w-full items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 py-1 pl-2.5 pr-1 text-xs text-slate-700">
              {item.ref ? <Icon name="paperclip" size={14} className="shrink-0 text-slate-400" /> : <Spinner size={14} className="shrink-0 text-slate-400" />}
              <span className="truncate">{item.filename}</span>
              <span className="shrink-0 text-slate-400">{formatBytes(item.size)}</span>
              <Button variant="ghost" size="sm" icon="x" title={`Remove ${item.filename}`} onClick={() => uploads.remove(item.id)} className="h-6 w-6" />
            </li>
          ))}
        </ul>
      )}
      <Button variant="ghost" size="sm" icon="paperclip" disabled={disabled} onClick={() => input.current?.click()}>
        Attach files
      </Button>
    </div>
  );
}
