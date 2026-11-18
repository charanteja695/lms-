import { Link } from "react-router-dom";

import { formatRelative } from "@/core/lib/format";
import { ScoreRing } from "@/modules/career/resumes/components/common/ScoreRing";
import type { Resume } from "@/modules/career/resumes/types";
import { Badge, Icon, Menu } from "@/shared/ui";

/** One resume: a page-shaped thumbnail with its live ATS score, what it is for, and when it last changed. */
export function ResumeCard({ resume, templateName, levelLabel, onDuplicate, onDelete }: {
  resume: Resume;
  templateName: string;
  levelLabel: string;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  return (
    <article className="group relative flex flex-col overflow-hidden rounded-xl bg-white border border-[#E5E7EB] shadow-xs transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm">
      <Link to={`/career/resumes/${resume.resume_id}`} className="flex flex-1 flex-col focus-visible:outline-none" aria-label={`Open ${resume.title}`}>
        <div className="relative flex h-40 justify-center overflow-hidden bg-slate-50 pt-4 border-b border-[#E5E7EB]">
          <div aria-hidden="true" className="flex w-32 flex-col gap-1.5 rounded-t bg-white px-3 pt-3 shadow-xs border border-b-0 border-[#E5E7EB]">
            <span className="h-1.5 w-2/3 rounded-sm bg-[#111827]" />
            <span className="h-1 w-5/6 rounded-sm bg-slate-300" />
            <span className="mt-1.5 h-1 w-2/5 rounded-sm bg-[#635BFF]" />
            <span className="h-1 w-full rounded-sm bg-slate-200" />
            <span className="h-1 w-11/12 rounded-sm bg-slate-200" />
            <span className="mt-1.5 h-1 w-1/3 rounded-sm bg-[#635BFF]" />
            <span className="h-1 w-full rounded-sm bg-slate-200" />
            <span className="h-1 w-4/5 rounded-sm bg-slate-200" />
          </div>
          {resume.ats_score != null && <ScoreRing score={resume.ats_score} size={52} className="absolute bottom-3 right-3 shadow-xs" />}
          {resume.shared && <Badge tone="green" className="absolute left-3 top-3">Shared link on</Badge>}
        </div>
        <div className="flex flex-col gap-1 p-5">
          <h3 className="truncate text-[16px] font-semibold text-[#111827]">{resume.title}</h3>
          <p className="truncate text-[12px] text-[#64748B]">{[resume.target_role, levelLabel, templateName].filter(Boolean).join(" · ")}</p>
          <p className="text-[12px] text-[#64748B]">Edited {formatRelative(resume.updated_at)}{resume.latest_version_no ? ` · ${resume.latest_version_no} saved versions` : ""}</p>
        </div>
      </Link>
      <div className="absolute right-2 top-2">
        <Menu
          trigger={
            <button type="button" aria-label={`More for ${resume.title}`} className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/95 text-slate-600 shadow-xs hover:text-[#111827] cursor-pointer">
              <Icon name="more" size={16} />
            </button>
          }
          items={[
            { label: "Copy for another role", icon: "layers", onSelect: onDuplicate },
            { label: "Delete", icon: "trash", tone: "danger", onSelect: onDelete },
          ]}
        />
      </div>
    </article>
  );
}
