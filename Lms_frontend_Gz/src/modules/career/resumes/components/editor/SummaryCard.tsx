import { cn } from "@/core/lib/cn";
import type { Draft } from "@/modules/career/resumes/types";
import { Checkbox, Textarea } from "@/shared/ui";

/** Summary (empty = the profile's) and which contact details print. AI help for it lives in the tools panel. */
export function SummaryBlock({ draft, open, onOpen, onChange }: { resumeId: string; draft: Draft; open: boolean; onOpen: () => void; onChange: (draft: Draft) => void }) {
  const setSummary = (next: Partial<Draft["summary"]>) => onChange({ ...draft, summary: { ...draft.summary, ...next } });
  const setPersonal = (next: Partial<Draft["personal"]>) => onChange({ ...draft, personal: { ...draft.personal, ...next } });
  return (
    <div className={cn("rounded-xl transition-colors", open ? "bg-slate-50 ring-1 ring-brand-200" : "hover:bg-slate-50")}>
      <button type="button" onClick={onOpen} aria-expanded={open} className="flex min-h-[48px] w-full flex-col justify-center px-3 text-left">
        <span className="text-sm font-bold text-navy-950">Summary &amp; contact</span>
        <span className="text-xs text-slate-500">{draft.summary.visible ? (draft.summary.text ? "Written for this resume" : "Uses your profile summary") : "No summary"}</span>
      </button>
      {open && (
        <div className="space-y-3 px-3 pb-3">
          <Checkbox label="Show a summary" checked={draft.summary.visible} onChange={(e) => setSummary({ visible: e.target.checked })} />
          {draft.summary.visible && (
            <Textarea aria-label="Summary" rows={4} maxLength={1000} placeholder="Leave empty to use your profile's summary, or ask the AI in the panel on the right." value={draft.summary.text ?? ""} onChange={(e) => setSummary({ text: e.target.value || null })} />
          )}
          <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-slate-200 pt-2">
            <Checkbox label="Phone" checked={draft.personal.show_phone} onChange={(e) => setPersonal({ show_phone: e.target.checked })} />
            <Checkbox label="Location" checked={draft.personal.show_location} onChange={(e) => setPersonal({ show_location: e.target.checked })} />
            <Checkbox label="Links" checked={draft.personal.show_links} onChange={(e) => setPersonal({ show_links: e.target.checked })} />
          </div>
        </div>
      )}
    </div>
  );
}
