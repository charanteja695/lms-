import { cn } from "@/core/lib/cn";
import { MESSAGE_KIND_BADGES } from "@/modules/ai-tutor/common/labels";
import { CitationList } from "@/modules/ai-tutor/chat/components/CitationList";
import { MessageFeedback } from "@/modules/ai-tutor/chat/components/MessageFeedback";
import type { TutorMessage } from "@/modules/ai-tutor/chat/types";
import { Badge } from "@/shared/ui";

export function MessageBubble({ message }: { message: TutorMessage }) {
  const mine = message.role === "user";
  const badge = mine ? undefined : MESSAGE_KIND_BADGES[message.kind];

  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-[85%] rounded-2xl px-4 py-3 text-sm", mine ? "bg-brand-600 text-white" : "border border-slate-200 bg-white text-slate-800")}>
        {(badge || message.hint_level != null) && (
          <div className="mb-1.5 flex flex-wrap gap-1">
            {badge && <Badge tone={badge.tone}>{badge.label}</Badge>}
            {message.hint_level != null && <Badge tone="purple">Hint {message.hint_level}</Badge>}
          </div>
        )}
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        {!mine && message.citations && <CitationList citations={message.citations} />}
        {!mine && message.kind !== "escalation" && message.kind !== "blocked" && <MessageFeedback messageId={message.message_id} />}
      </div>
    </div>
  );
}

/** The in-flight turn: what the student just sent and the answer as it streams in. */
export function PendingTurn({ userText, streamed }: { userText: string; streamed: string }) {
  return (
    <>
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl bg-brand-600 px-4 py-3 text-sm text-white">
          <p className="whitespace-pre-wrap break-words">{userText}</p>
        </div>
      </div>
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800">
          <p className="whitespace-pre-wrap break-words">{streamed || <span className="text-slate-400">Thinking…</span>}</p>
        </div>
      </div>
    </>
  );
}
