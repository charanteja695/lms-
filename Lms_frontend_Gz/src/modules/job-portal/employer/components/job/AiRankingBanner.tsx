import type { Ranking } from "@/modules/job-portal/employer/pipelineTypes";
import { Icon } from "@/shared/ui";

/** The AI's ranking of new applicants in one line, with a button that only *selects* its shortlist — a person still decides. */
export function AiRankingBanner({ ranking, onSelect }: { ranking: Ranking; onSelect: (ids: string[]) => void }) {
  const ranked = ranking.shortlist.length + ranking.review.length + ranking.reject.length;
  if (ranked === 0 && ranking.unscreened.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-2xl bg-navy-50 p-4 ring-1 ring-navy-100">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-navy-900 ring-1 ring-navy-100"><Icon name="sparkles" size={18} /></span>
      <p className="min-w-[240px] flex-1 text-sm leading-relaxed text-slate-700">
        <strong className="text-navy-950">AI ranked {ranked} new applicant{ranked === 1 ? "" : "s"}.</strong>{" "}
        It suggests shortlisting {ranking.shortlist.length}, a closer look at {ranking.review.length}, and not moving {ranking.reject.length} forward
        {ranking.unscreened.length > 0 ? ` (${ranking.unscreened.length} not screened yet)` : ""}. {ranking.note}
      </p>
      <button
        type="button"
        disabled={ranking.shortlist.length === 0}
        onClick={() => onSelect(ranking.shortlist.map((a) => a.application_id))}
        className="h-10 rounded-xl bg-white px-4 text-sm font-bold text-navy-950 ring-1 ring-navy-200 hover:bg-navy-50 disabled:opacity-50"
      >
        Select AI's shortlist
      </button>
    </div>
  );
}
