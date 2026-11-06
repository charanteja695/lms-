import { useState } from "react";

import { cn } from "@/core/lib/cn";
import { useNotify } from "@/core/hooks/useNotify";
import { useAiPolishMutation, useAiSummaryMutation, type Suggestion } from "@/modules/career/resumes/api/resumeToolsApi";
import { GrammarPanel } from "@/modules/career/resumes/components/tools/GrammarPanel";
import { SuggestionList } from "@/modules/career/resumes/components/tools/SuggestionList";
import type { Option } from "@/modules/career/resumes/types";
import { Button } from "@/shared/ui";

/** AI help with the words: a summary from the student's facts, polishing their own, and the writing checks. */
export function WriteTab({ resumeId, summaryText, tones, onUseSummary }: { resumeId: string; summaryText: string; tones: Option[]; onUseSummary: (text: string) => void }) {
  const notify = useNotify();
  const [tone, setTone] = useState(tones[0]?.key ?? "");
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [suggest, { isLoading: suggesting }] = useAiSummaryMutation();
  const [polish, { isLoading: polishing }] = useAiPolishMutation();
  const run = async (work: () => Promise<Suggestion>) => {
    try {
      setSuggestion(await work());
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <div className="space-y-5">
      <section className="space-y-3">
        <h3 className="text-sm font-bold text-navy-950">Summary</h3>
        <div role="radiogroup" aria-label="Tone" className="flex flex-wrap gap-1.5">
          {tones.map((option) => (
            <button
              key={option.key}
              type="button"
              role="radio"
              aria-checked={option.key === tone}
              title={option.note}
              onClick={() => setTone(option.key)}
              className={cn("min-h-[36px] rounded-full px-3 text-[13px] font-semibold", option.key === tone ? "bg-brand-50 text-brand-800 ring-1 ring-brand-500" : "text-slate-600 ring-1 ring-slate-200 hover:text-navy-950")}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button icon="sparkles" loading={suggesting} onClick={() => void run(() => suggest({ resumeId, tone }).unwrap())}>Write my summary</Button>
          <Button variant="secondary" loading={polishing} disabled={!summaryText.trim()} onClick={() => void run(() => polish({ resumeId, text: summaryText, tone }).unwrap())}>Polish mine</Button>
        </div>
        {suggestion && <SuggestionList suggestions={[suggestion]} onApply={(text) => { onUseSummary(text); setSuggestion(null); }} />}
      </section>
      <section className="space-y-2 border-t border-slate-100 pt-4">
        <h3 className="text-sm font-bold text-navy-950">Points under each entry</h3>
        <p className="text-[13px] text-slate-600">Open a section on the left, click an entry's points, then <strong>Improve with AI</strong>. It rewrites them with action words and never adds a number you didn't give.</p>
      </section>
      <section className="space-y-2 border-t border-slate-100 pt-4">
        <h3 className="text-sm font-bold text-navy-950">Writing checks</h3>
        <GrammarPanel resumeId={resumeId} />
      </section>
    </div>
  );
}
