import { useState } from "react";

import { cn } from "@/core/lib/cn";
import { ROUND_LABELS } from "@/modules/ai-interview/common/labels";
import type { Report } from "@/modules/ai-interview/student/api/studentInterviewsApi";
import { Icon } from "@/shared/ui";

/** Each round: its score, the AI's comment, and the candidate's own words it rests on. Open one at a time. */
export function RoundFeedback({ report }: { report: Report }) {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <ul className="space-y-2">
      {report.rounds.map((round, index) => {
        const isOpen = open === index;
        const low = round.score != null && round.score < report.score_max * 0.6;
        return (
          <li key={`${round.round}-${index}`} className="overflow-hidden rounded-2xl bg-white ring-1 ring-slate-200/70">
            <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : index)} className="flex min-h-[56px] w-full items-center gap-3 px-4 text-left">
              <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-extrabold", low ? "bg-accent-50 text-accent-700" : "bg-brand-50 text-brand-800")}>{round.score ?? "—"}</span>
              <span className="flex-1 text-sm font-bold text-navy-950">Round {index + 1} · {ROUND_LABELS[round.type] ?? round.type}</span>
              <Icon name={isOpen ? "chevronDown" : "chevronRight"} size={16} className="text-slate-400" />
            </button>
            {isOpen && (
              <div className="space-y-2 border-t border-slate-100 px-4 py-3 text-[13px] leading-relaxed text-slate-700">
                {round.comment && <p>{round.comment}</p>}
                {round.quotes.length > 0 && (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-500">What you said</p>
                    <ul className="mt-1 space-y-1">{round.quotes.map((q) => <li key={q} className="rounded-lg bg-slate-50 px-3 py-1.5 italic">“{q}”</li>)}</ul>
                  </div>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
