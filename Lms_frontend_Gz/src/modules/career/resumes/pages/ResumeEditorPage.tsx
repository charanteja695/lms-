import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ResumeDocumentView } from "@/modules/career/common/components/ResumeDocumentView";
import { useGetMyCareerProfileQuery } from "@/modules/career/profile/api/profileApi";
import { useGetResumeOptionsQuery, useGetResumeQuery, useListResumeTemplatesQuery } from "@/modules/career/resumes/api/resumesApi";
import { EditorHeader } from "@/modules/career/resumes/components/editor/EditorHeader";
import { SectionsCard } from "@/modules/career/resumes/components/editor/SectionsCard";
import type { FixTarget } from "@/modules/career/resumes/components/tools/ScoreTab";
import { ShareDialog } from "@/modules/career/resumes/components/tools/ShareDialog";
import { ToolsPanel, type ToolTab } from "@/modules/career/resumes/components/tools/ToolsPanel";
import { useResumeDraft } from "@/modules/career/resumes/hooks/useResumeDraft";
import { EmptyState, PageLoader } from "@/shared/ui";

/** One workspace: sections on the left, the live page in the middle, score / job match / AI on the right. Saves itself. */
export function ResumeEditorPage() {
  const { resumeId = "" } = useParams();
  const navigate = useNavigate();
  const { data: detail, isLoading, isError, refetch } = useGetResumeQuery(resumeId, { skip: !resumeId });
  const { data: profile } = useGetMyCareerProfileQuery();
  const { data: options } = useGetResumeOptionsQuery();
  const { data: templates = [] } = useListResumeTemplatesQuery();
  const editor = useResumeDraft(detail, refetch);
  const [open, setOpen] = useState<string | null>(null);
  const [focusItem, setFocusItem] = useState<string | null>(null);
  const [tab, setTab] = useState<ToolTab>("score");
  const [sharing, setSharing] = useState(false);

  if (isLoading || !options) return <PageLoader />;
  if (isError || !detail) return <EmptyState icon="alert" title="Resume not found" description="It may have been deleted." />;
  const { draft } = editor;

  const applySummary = (text: string) => draft && editor.change({ ...draft, summary: { text, visible: true } });
  const fix = (target: FixTarget) => {
    if ("tab" in target) setTab(target.tab);
    else if ("section" in target) { setOpen(target.section); setFocusItem(target.itemId); }
    else navigate("/career/profile");
  };

  return (
    <>
      <EditorHeader
        meta={editor.meta}
        status={editor.status}
        level={detail.resume.experience_level}
        levels={options.experience_levels}
        templates={templates}
        onMeta={editor.changeMeta}
        onLevel={(level) => void editor.changeLevel(level)}
        onRetry={editor.retry}
        onShare={() => setSharing(true)}
      />
      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_340px]">
        <div className="min-w-0 xl:sticky xl:top-20 xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto">
          {draft && (
            <SectionsCard
              resumeId={resumeId}
              draft={draft}
              profileItems={profile?.items ?? []}
              open={open}
              focusItemId={focusItem}
              onOpen={(key) => { setOpen(key); setFocusItem(null); }}
              onChange={editor.change}
            />
          )}
        </div>
        <section aria-label="Preview" className="min-w-0 rounded-2xl bg-slate-100 p-3 sm:p-6">
          <div className="mx-auto max-w-[680px] shadow-lift">
            <ResumeDocumentView document={detail.document} />
          </div>
        </section>
        <div className="min-w-0 xl:sticky xl:top-20 xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto">
          <ToolsPanel
            tab={tab}
            onTab={setTab}
            resumeId={resumeId}
            ats={detail.ats}
            jobDescription={editor.meta.job_description ?? ""}
            summaryText={draft?.summary.text ?? ""}
            tones={options.ai_tones}
            onFix={fix}
            onJobDescription={(text) => editor.changeMeta({ job_description: text })}
            onUseSummary={applySummary}
          />
        </div>
      </div>
      {sharing && <ShareDialog resume={detail.resume} options={options} onClose={() => setSharing(false)} />}
    </>
  );
}
