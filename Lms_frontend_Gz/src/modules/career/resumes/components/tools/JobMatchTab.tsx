import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useAiTailorMutation, type KeywordGap, type Suggestion } from "@/modules/career/resumes/api/resumeToolsApi";
import { SuggestionList } from "@/modules/career/resumes/components/tools/SuggestionList";
import { Button, Textarea } from "@/shared/ui";

/** Paste a job post (saved on the resume), see which of its keywords the resume has, and get a summary aimed at it. */
export function JobMatchTab({ resumeId, jobDescription, onJobDescription, onUseSummary }: {
  resumeId: string;
  jobDescription: string;
  onJobDescription: (text: string | null) => void;
  onUseSummary: (text: string) => void;
}) {
  const notify = useNotify();
  const [tailor, { isLoading, originalArgs }] = useAiTailorMutation();
  const [gap, setGap] = useState<KeywordGap | null>(null);
  const [summary, setSummary] = useState<Suggestion | null>(null);

  const run = async (includeSummary: boolean) => {
    try {
      const result = await tailor({ resumeId, job_description: jobDescription, include_summary: includeSummary }).unwrap();
      setGap(result.gap);
      setSummary(result.summary);
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <div className="space-y-4">
      <Textarea
        aria-label="Job description"
        rows={5}
        maxLength={8000}
        placeholder="Paste the job post you're applying to"
        value={jobDescription}
        onChange={(e) => onJobDescription(e.target.value || null)}
      />
      <Button fullWidth loading={isLoading && !originalArgs?.include_summary} disabled={!jobDescription.trim()} onClick={() => void run(false)}>Check my match</Button>
      {gap && (
        <div className="space-y-3">
          <p role="status" className="text-[15px] font-bold text-navy-950">{gap.match_percent}% of the job's keywords are on this resume</p>
          <div className="flex flex-wrap gap-1.5">
            {gap.keywords.filter((k) => k.present).map((k) => <span key={k.term} className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-800">✓ {k.term}</span>)}
          </div>
          {gap.add_from_profile.length > 0 && (
            <div className="rounded-xl bg-amber-50 p-3 ring-1 ring-amber-200">
              <p className="text-[13px] font-bold text-amber-900">In your profile — add them here</p>
              <p className="mt-1 text-[13px] text-slate-700">{gap.add_from_profile.join(", ")}. Tick the entry that mentions them in Sections, or reword a point.</p>
            </div>
          )}
          {gap.not_in_profile.length > 0 && (
            <div className="rounded-xl bg-accent-50 p-3 ring-1 ring-accent-200">
              <p className="text-[13px] font-bold text-accent-800">Missing — add only if true</p>
              <p className="mt-1 text-[13px] text-slate-700">{gap.not_in_profile.join(", ")}</p>
            </div>
          )}
          <Button variant="secondary" icon="sparkles" fullWidth loading={isLoading && originalArgs?.include_summary} onClick={() => void run(true)}>Write a summary for this job</Button>
          {summary && <SuggestionList suggestions={[summary]} onApply={(text) => { onUseSummary(text); setSummary(null); }} />}
        </div>
      )}
    </div>
  );
}
