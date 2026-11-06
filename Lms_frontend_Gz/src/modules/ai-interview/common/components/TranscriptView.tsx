import { cn } from "@/core/lib/cn";
import type { Turn } from "@/modules/ai-interview/common/types";

/** An interview's turns: the interviewer's questions, the candidate's answers, code and what it printed, system notes. */
export function TranscriptView({ turns }: { turns: Turn[] }) {
  return (
    <ol className="space-y-3">
      {turns.map((turn) => {
        if (turn.speaker === "system" && turn.kind === "note") return <li key={turn.seq} className="text-center text-xs text-slate-400">{turn.text}</li>;
        const candidate = turn.speaker === "candidate";
        const code = turn.kind === "code" || turn.kind === "code_result";
        return (
          <li key={turn.seq} className={cn("flex", candidate ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[85%] rounded-2xl px-4 py-2.5 text-sm", candidate ? "bg-brand-600 text-white" : "border border-slate-200 bg-white text-slate-800", code && "font-mono text-xs")}>
              {turn.kind === "follow_up" && <p className="mb-0.5 text-xs text-slate-400">Follow-up</p>}
              {turn.kind === "code" && <p className="mb-1 font-sans text-xs opacity-75">Code ({String(turn.meta?.language ?? "")})</p>}
              {turn.kind === "code_result" && <p className="mb-1 font-sans text-xs text-slate-400">Output · {String(turn.meta?.outcome ?? "")}</p>}
              <p className="whitespace-pre-wrap break-words">{turn.text}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
