import { Link } from "react-router-dom";

import { cn } from "@/core/lib/cn";
import type { Meta, SaveStatus } from "@/modules/career/resumes/hooks/useResumeDraft";
import type { Option, ResumeTemplate } from "@/modules/career/resumes/types";
import { Button, Icon } from "@/shared/ui";

const STATUS: Record<SaveStatus, { text: string; tone: string }> = {
  saved: { text: "Saved", tone: "text-brand-700" },
  pending: { text: "Editing…", tone: "text-slate-500" },
  saving: { text: "Saving…", tone: "text-slate-500" },
  error: { text: "Not saved — retry", tone: "text-red-600" },
};

/** Name, save state, experience level and look, and the one export button — the whole toolbar of the editor. */
export function EditorHeader({ meta, status, level, levels, templates, onMeta, onLevel, onRetry, onShare }: {
  meta: Meta;
  status: SaveStatus;
  level: string;
  levels: Option[];
  templates: ResumeTemplate[];
  onMeta: (next: Partial<Meta>) => void;
  onLevel: (level: string) => void;
  onRetry: () => void;
  onShare: () => void;
}) {
  const state = STATUS[status];
  return (
    <div className="mb-5 flex flex-wrap items-center gap-3 rounded-2xl bg-white px-4 py-3 shadow-card ring-1 ring-slate-200/60">
      <Link to="/career/resumes" className="flex h-10 items-center gap-1.5 rounded-xl px-2.5 text-sm font-semibold text-slate-600 ring-1 ring-slate-200 hover:text-navy-950">
        <Icon name="chevronLeft" size={16} />Resumes
      </Link>
      <div className="flex min-w-[200px] flex-1 flex-col">
        <input
          aria-label="Resume name"
          value={meta.title ?? ""}
          maxLength={120}
          onChange={(e) => onMeta({ title: e.target.value })}
          className="w-full rounded-lg border border-transparent bg-transparent px-1.5 py-0.5 text-[17px] font-bold text-navy-950 hover:border-slate-200 focus:border-brand-500 focus:outline-none"
        />
        <button type="button" onClick={status === "error" ? onRetry : undefined} className={cn("px-1.5 text-left text-xs font-semibold", state.tone)} aria-live="polite">
          {state.text}
        </button>
      </div>
      <div role="radiogroup" aria-label="Experience" className="flex flex-wrap gap-1 rounded-xl bg-slate-100/80 p-1 ring-1 ring-slate-200/60">
        {levels.map((option) => (
          <button
            key={option.key}
            type="button"
            role="radio"
            aria-checked={option.key === level}
            title={option.note}
            onClick={() => option.key !== level && onLevel(option.key)}
            className={cn("h-8 rounded-lg px-2.5 text-[13px] font-semibold", option.key === level ? "bg-white text-navy-950 shadow-card" : "text-slate-600 hover:text-navy-950")}
          >
            {option.label}
          </button>
        ))}
      </div>
      <label className="flex items-center gap-2 text-[13px] font-semibold text-slate-600">
        Look
        <select
          value={meta.template_key ?? ""}
          onChange={(e) => onMeta({ template_key: e.target.value })}
          className="h-10 rounded-xl border border-slate-200 bg-white px-2.5 text-sm text-navy-950 focus:border-brand-500 focus:outline-none"
        >
          {templates.map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}
        </select>
      </label>
      <Button icon="download" onClick={onShare}>Download / share</Button>
    </div>
  );
}
