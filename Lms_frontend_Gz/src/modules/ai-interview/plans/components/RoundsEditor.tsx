import { toOptions } from "@/core/lib/options";
import { ROUND_LABELS } from "@/modules/ai-interview/common/labels";
import type { RoundType } from "@/modules/ai-interview/common/types";
import type { RoundDraft } from "@/modules/ai-interview/plans/form/planForm";
import { Button, Field, Icon, Input, Select, Textarea } from "@/shared/ui";

/** Rounds in order. Core questions are asked to every candidate verbatim and in order; the interviewer adds follow-ups. */
export function RoundsEditor({ rounds, onChange }: { rounds: RoundDraft[]; onChange: (rounds: RoundDraft[]) => void }) {
  const set = (index: number, next: Partial<RoundDraft>) => onChange(rounds.map((r, i) => (i === index ? { ...r, ...next } : r)));
  const move = (index: number, delta: number) => {
    const next = [...rounds];
    [next[index], next[index + delta]] = [next[index + delta]!, next[index]!];
    onChange(next);
  };
  const total = rounds.reduce((sum, r) => sum + (Number(r.minutes) || 0), 0);

  return (
    <div className="space-y-3">
      {rounds.map((round, index) => (
        <div key={index} className="space-y-3 rounded-lg border border-slate-200 p-3">
          <div className="flex flex-wrap items-end gap-3">
            <Field label={`Round ${index + 1}`}>{(p) => <Select {...p} className="w-48" value={round.type} options={toOptions(ROUND_LABELS)} onChange={(e) => set(index, { type: e.target.value as RoundType })} />}</Field>
            <Field label="Minutes">{(p) => <Input {...p} type="number" min={1} className="w-24" value={round.minutes} onChange={(e) => set(index, { minutes: e.target.value })} />}</Field>
            <span className="flex-1" />
            <Button variant="ghost" size="icon" aria-label="Move up" disabled={index === 0} onClick={() => move(index, -1)}><Icon name="arrowUp" size={14} /></Button>
            <Button variant="ghost" size="icon" aria-label="Move down" disabled={index === rounds.length - 1} onClick={() => move(index, 1)}><Icon name="arrowDown" size={14} /></Button>
            <Button variant="ghost" size="icon" aria-label="Remove round" disabled={rounds.length === 1} onClick={() => onChange(rounds.filter((_, i) => i !== index))}><Icon name="trash" size={14} /></Button>
          </div>
          <Field label="Core questions" hint="One per line.">{(p) => <Textarea {...p} rows={3} value={round.questions} onChange={(e) => set(index, { questions: e.target.value })} />}</Field>
          {round.type === "coding" && <Field label="Languages" hint="Comma separated codes from the compiler, e.g. python3, java.">{(p) => <Input {...p} value={round.languages} onChange={(e) => set(index, { languages: e.target.value })} />}</Field>}
        </div>
      ))}
      <div className="flex items-center justify-between">
        <Button variant="secondary" size="sm" icon="plus" onClick={() => onChange([...rounds, { type: "technical", minutes: "10", questions: "", languages: "" }])}>Add round</Button>
        <span className="text-xs text-slate-500">Rounds total {total} min</span>
      </div>
    </div>
  );
}
