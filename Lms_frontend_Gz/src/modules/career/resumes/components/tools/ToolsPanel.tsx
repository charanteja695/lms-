import { JobMatchTab } from "@/modules/career/resumes/components/tools/JobMatchTab";
import { ScoreTab, type FixTarget } from "@/modules/career/resumes/components/tools/ScoreTab";
import { WriteTab } from "@/modules/career/resumes/components/tools/WriteTab";
import type { AtsResult, Option } from "@/modules/career/resumes/types";
import { Tabs } from "@/shared/ui";

export type ToolTab = "score" | "job" | "write";

/** The right panel: Score (with the path to 100), Job match and AI writing help. */
export function ToolsPanel({ tab, onTab, resumeId, ats, jobDescription, summaryText, tones, onFix, onJobDescription, onUseSummary }: {
  tab: ToolTab;
  onTab: (tab: ToolTab) => void;
  resumeId: string;
  ats: AtsResult;
  jobDescription: string;
  summaryText: string;
  tones: Option[];
  onFix: (target: FixTarget) => void;
  onJobDescription: (text: string | null) => void;
  onUseSummary: (text: string) => void;
}) {
  return (
    <aside aria-label="Make it stronger" className="min-w-0 space-y-4 rounded-2xl bg-white p-4 shadow-card ring-1 ring-slate-200/60">
      <Tabs variant="pills" value={tab} onChange={onTab} tabs={[{ value: "score", label: `Score ${ats.score}` }, { value: "job", label: "Job match" }, { value: "write", label: "AI write" }]} />
      {tab === "score" && <ScoreTab ats={ats} onFix={onFix} />}
      {tab === "job" && <JobMatchTab resumeId={resumeId} jobDescription={jobDescription} onJobDescription={onJobDescription} onUseSummary={onUseSummary} />}
      {tab === "write" && <WriteTab resumeId={resumeId} summaryText={summaryText} tones={tones} onUseSummary={onUseSummary} />}
    </aside>
  );
}
