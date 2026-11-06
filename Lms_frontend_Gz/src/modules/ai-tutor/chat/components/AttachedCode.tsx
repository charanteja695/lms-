import type { TutorAttachment } from "@/core/lib/storage";
import { Button, Icon } from "@/shared/ui";

/** The code the student brought from a coding screen; sent with each question until they remove it. */
export function AttachedCode({ attachment, onRemove }: { attachment: TutorAttachment; onRemove: () => void }) {
  const lines = attachment.code.split("\n").length;
  return (
    <div className="flex items-center justify-between gap-3 border-t border-slate-200 bg-brand-50/60 px-4 py-2 text-sm">
      <span className="flex min-w-0 items-center gap-2 text-slate-700">
        <Icon name="terminal" size={16} className="shrink-0 text-brand-700" />
        <span className="truncate">Your code from <span className="font-medium">{attachment.title}</span> ({attachment.language}, {lines} line{lines === 1 ? "" : "s"}) is shared with the tutor</span>
      </span>
      <Button size="sm" variant="ghost" icon="x" aria-label="Stop sharing this code" onClick={onRemove} />
    </div>
  );
}
