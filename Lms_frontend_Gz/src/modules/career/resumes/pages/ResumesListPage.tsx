import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import {
  useDeleteResumeMutation,
  useDuplicateResumeMutation,
  useGetResumeOptionsQuery,
  useListResumesQuery,
  useListResumeTemplatesQuery,
} from "@/modules/career/resumes/api/resumesApi";
import { ResumeCard } from "@/modules/career/resumes/components/list/ResumeCard";
import { NewResumeDialog } from "@/modules/career/resumes/components/NewResumeDialog";
import { Button, ConfirmDialog, EmptyState, Icon, PageHeader, PageLoader } from "@/shared/ui";

export function ResumesListPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data, isLoading } = useListResumesQuery({ per_page: 50 });
  const { data: options } = useGetResumeOptionsQuery();
  const canCreate = useCan().acts("my_career.create", "career.profile");
  const { data: templates = [] } = useListResumeTemplatesQuery();
  const [duplicate] = useDuplicateResumeMutation();
  const [remove] = useDeleteResumeMutation();
  const [creating, setCreating] = useState(false);

  if (isLoading) return <PageLoader />;
  const resumes = data?.items ?? [];
  const max = options?.max_resumes ?? 0;
  const full = max > 0 && resumes.length >= max;
  const templateName = (key: string) => templates.find((t) => t.key === key)?.name ?? key;
  const levelLabel = (key: string) => options?.experience_levels.find((l) => l.key === key)?.label ?? "";

  return (
    <>
      <PageHeader
        title="Resumes"
        description="Your certificates, courses and test scores are already filled in. Make one resume for each role you apply to."
        actions={canCreate ? <Button icon="plus" disabled={full} onClick={() => setCreating(true)}>New resume</Button> : undefined}
      />

      {resumes.length === 0 ? (
        <EmptyState
          icon="fileText"
          title="No resumes yet"
          description="Start from your profile, or upload your old resume or LinkedIn PDF — it takes a minute."
          action={canCreate ? <Button icon="plus" onClick={() => setCreating(true)}>Create my first resume</Button> : undefined}
        />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {resumes.map((resume) => (
            <ResumeCard
              key={resume.resume_id}
              resume={resume}
              templateName={templateName(resume.template_key)}
              levelLabel={levelLabel(resume.experience_level)}
              onDuplicate={() => void duplicate(resume.resume_id).unwrap().then(() => notify.success("Copied — rename it for the new role"), notify.apiError)}
              onDelete={() =>
                confirm.ask({ title: `Delete "${resume.title}"?`, description: "Its saved versions go too, and any share link stops working.", confirmLabel: "Delete" }, async () => {
                  await remove(resume.resume_id).unwrap().catch(notify.apiError);
                })
              }
            />
          ))}
          {!full && (
            <button
              type="button"
              onClick={() => setCreating(true)}
              className="flex min-h-[260px] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white p-6 text-center transition-colors hover:border-brand-400 hover:bg-brand-50/40"
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700"><Icon name="plus" size={22} /></span>
              <span className="text-[15px] font-bold text-navy-950">New resume for another role</span>
              <span className="max-w-[220px] text-[13px] text-slate-500">{max ? `${resumes.length} of ${max} used` : ""}</span>
            </button>
          )}
        </div>
      )}

      {creating && options && (
        <NewResumeDialog options={options} onClose={() => setCreating(false)} onCreated={(resume) => navigate(`/career/resumes/${resume.resume_id}`)} />
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
