import type { Citation } from "@/modules/ai-tutor/chat/types";
import { Icon } from "@/shared/ui";

function timestamp(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** The sources an answer was grounded in: lessons (with the video moment when it came from a transcript) or FAQ entries. */
export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <ul className="mt-3 space-y-1 border-t border-slate-200/70 pt-2 text-xs text-slate-600">
      {citations.map((citation, index) =>
        citation.type === "lesson" ? (
          <li key={index} className="flex items-start gap-1.5">
            <span className="font-medium text-slate-500">[{citation.number}]</span>
            <span>
              {citation.item_title}
              {(citation.module_title || citation.topic_title) && (
                <span className="text-slate-400"> · {[citation.module_title, citation.topic_title].filter(Boolean).join(" › ")}</span>
              )}
              {citation.source === "transcript" && citation.start_seconds != null && <span className="text-slate-400"> · at {timestamp(citation.start_seconds)}</span>}
            </span>
          </li>
        ) : (
          <li key={index} className="flex items-start gap-1.5">
            <Icon name="helpCircle" size={13} className="mt-0.5 shrink-0 text-slate-400" />
            <span>FAQ: {citation.question}</span>
          </li>
        ),
      )}
    </ul>
  );
}
