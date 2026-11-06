import { useState } from "react";

import type { ProfileItem } from "@/modules/career/profile/types";
import { SectionEditor } from "@/modules/career/resumes/components/editor/SectionEditor";
import { SummaryBlock } from "@/modules/career/resumes/components/editor/SummaryCard";
import type { Draft } from "@/modules/career/resumes/types";

/** The left panel: summary and contact, then the sections in print order — drag (or the arrows) to reorder. */
export function SectionsCard({ resumeId, draft, profileItems, open, focusItemId, onOpen, onChange }: {
  resumeId: string;
  draft: Draft;
  profileItems: ProfileItem[];
  open: string | null;
  focusItemId: string | null;
  onOpen: (key: string | null) => void;
  onChange: (draft: Draft) => void;
}) {
  const [dragging, setDragging] = useState<number | null>(null);
  const move = (from: number, to: number) => {
    if (to < 0 || to >= draft.sections.length || from === to) return;
    const sections = [...draft.sections];
    const [moved] = sections.splice(from, 1);
    sections.splice(to, 0, moved!);
    onChange({ ...draft, sections });
  };

  return (
    <nav aria-label="Resume sections" className="space-y-2 rounded-2xl bg-white p-3 shadow-card ring-1 ring-slate-200/60">
      <div className="flex items-baseline justify-between px-1.5 pb-1">
        <h2 className="text-[15px] font-bold text-navy-950">Sections</h2>
        <span className="text-xs text-slate-500">Drag to reorder</span>
      </div>
      <SummaryBlock resumeId={resumeId} draft={draft} open={open === "summary"} onOpen={() => onOpen(open === "summary" ? null : "summary")} onChange={onChange} />
      {draft.sections.map((section, index) => (
        <SectionEditor
          key={section.key}
          resumeId={resumeId}
          section={section}
          profileItems={profileItems}
          open={open === section.key}
          focusItemId={focusItemId}
          onOpen={() => onOpen(open === section.key ? null : section.key)}
          onMove={(delta) => move(index, index + delta)}
          onChange={(next) => onChange({ ...draft, sections: draft.sections.map((s, i) => (i === index ? next : s)) })}
          dragProps={{
            draggable: true,
            onDragStart: () => setDragging(index),
            onDragOver: (event) => event.preventDefault(),
            onDrop: () => { if (dragging != null) move(dragging, index); setDragging(null); },
            onDragEnd: () => setDragging(null),
          }}
        />
      ))}
      <p className="rounded-xl bg-slate-50 px-3 py-2.5 text-xs leading-relaxed text-slate-600">
        <span className="mr-1 rounded-full bg-brand-700 px-1.5 py-0.5 text-[10px] font-bold text-white">VERIFIED</span>
        entries come from your certificates and tests and can't be edited. Everything else you can reword for this resume.
      </p>
    </nav>
  );
}
