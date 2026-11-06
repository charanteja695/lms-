import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useAiRewriteMutation, type Suggestion } from "@/modules/career/resumes/api/resumeToolsApi";
import { SuggestionList } from "@/modules/career/resumes/components/tools/SuggestionList";
import { Button, Icon, Textarea } from "@/shared/ui";

/**
 * This resume's wording of an entry's points (the profile keeps its own; empty = the profile's). "Improve with AI" rewrites
 * them from the student's facts; a suggestion that adds a fact can't be applied.
 */
export function BulletsEditor({ resumeId, profileBullets, override, context, startOpen = false, onChange }: {
  resumeId: string;
  profileBullets: string[];
  override: string[] | null;
  context?: string;
  startOpen?: boolean;
  onChange: (bullets: string[] | null) => void;
}) {
  const notify = useNotify();
  const [open, setOpen] = useState(startOpen);
  const [rewrite, { isLoading }] = useAiRewriteMutation();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const current = override ?? profileBullets;
  const [text, setText] = useState(current.join("\n"));
  const edit = (value: string) => {
    setText(value);
    onChange(value.split("\n").map((line) => line.trim()).filter(Boolean).slice(0, 8));
  };

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="mt-1 block w-full rounded-md px-1 py-1 text-left hover:bg-slate-50">
        {current.length > 0
          ? <ul className="list-disc pl-5 text-[13px] text-slate-600">{current.map((bullet, index) => <li key={index}>{bullet}</li>)}</ul>
          : <span className="text-[13px] text-slate-500">No points yet</span>}
        <span className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-brand-700"><Icon name="edit" size={12} />Edit for this resume</span>
      </button>
    );
  }

  return (
    <div className="mt-2 space-y-2">
      <Textarea aria-label="Points for this resume, one per line" rows={Math.max(3, current.length + 1)} value={text} onChange={(event) => edit(event.target.value)} />
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          icon="sparkles"
          loading={isLoading}
          disabled={current.filter(Boolean).length === 0}
          onClick={async () => {
            try {
              setSuggestions(await rewrite({ resumeId, bullets: current.filter(Boolean).slice(0, 8), context }).unwrap());
            } catch (error) {
              notify.apiError(error);
            }
          }}
        >
          Improve with AI
        </Button>
        {override && <Button size="sm" variant="ghost" onClick={() => { setText(profileBullets.join("\n")); onChange(null); }}>Use profile wording</Button>}
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Done</Button>
      </div>
      {suggestions.length > 0 && (
        <SuggestionList
          suggestions={suggestions}
          onApply={(suggestionText, index) => {
            const next = [...current];
            next[index] = suggestionText;
            edit(next.join("\n"));
          }}
        />
      )}
    </div>
  );
}
