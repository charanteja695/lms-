import { useState } from "react";

import { ScoreRing } from "@/modules/career/resumes/components/common/ScoreRing";
import type { AtsResult } from "@/modules/career/resumes/types";
import { Button } from "@/shared/ui";

export type FixTarget = { tab: "job" | "write" } | { section: string; itemId: string | null } | { profile: true };

/** Where a fix is done: the server says which section or entry it is about; a few kinds of fix belong to another tab. */
function targetOf(fix: AtsResult["fixes"][number]): FixTarget {
  if (fix.code === "MISSING_KEYWORDS") return { tab: "job" };
  if (fix.section === "summary" || fix.code === "NO_SUMMARY") return { tab: "write" };
  if (fix.section && fix.section !== "keywords") return { section: fix.section, itemId: fix.item_id };
  return { profile: true };
}

/** The live score of the saved draft and its path to 100: each part short of full marks, what it adds, and its fixes. */
export function ScoreTab({ ats, onFix }: { ats: AtsResult; onFix: (target: FixTarget) => void }) {
  const [open, setOpen] = useState<string | null>(ats.path_to_100[0]?.key ?? null);
  const left = Math.max(0, 100 - ats.score);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <ScoreRing score={ats.score} size={76} />
        <div role="status" className="min-w-0">
          <p className="text-[15px] font-bold text-navy-950">{left === 0 ? "Every check passed" : `${left} points to 100`}</p>
          <p className="text-xs text-slate-500">{ats.word_count} words · updates as you edit · an estimate, not one company's system</p>
        </div>
      </div>
      {ats.path_to_100.length > 0 && <h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">Path to 100</h3>}
      <ul className="space-y-2">
        {ats.path_to_100.map((part) => {
          const fixes = ats.fixes.filter((f) => part.fix_codes.includes(f.code));
          const isOpen = open === part.key;
          return (
            <li key={part.key} className="rounded-xl ring-1 ring-slate-200">
              <button type="button" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : part.key)} className="flex min-h-[48px] w-full items-center justify-between gap-2 px-3 text-left">
                <span className="text-sm font-semibold text-navy-950">{part.label}</span>
                <span className="rounded-full bg-accent-50 px-2 py-0.5 text-xs font-bold text-accent-700">+{part.gain}</span>
              </button>
              {isOpen && (
                <ul className="space-y-2 border-t border-slate-100 p-3">
                  {fixes.length === 0 && <li className="text-[13px] text-slate-600">Nothing specific to change here — the points come as the resume grows.</li>}
                  {fixes.slice(0, 4).map((fix, index) => (
                    <li key={index} className="flex flex-col gap-1.5">
                      <span className="text-[13px] leading-snug text-slate-700 [overflow-wrap:anywhere]">{fix.message}</span>
                      <Button size="sm" variant="secondary" className="self-start" onClick={() => onFix(targetOf(fix))}>Fix it</Button>
                    </li>
                  ))}
                  {fixes.length > 4 && <li className="text-xs text-slate-500">and {fixes.length - 4} more like these</li>}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
