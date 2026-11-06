import { toOptions } from "@/core/lib/options";
import type { FillInBlank, ScoringMode } from "@/modules/assessments/questions/bodyTypes";
import { Button, Checkbox, Field, Icon, Input, Select } from "@/shared/ui";

const SCORING_LABELS: Record<ScoringMode, string> = { all_or_nothing: "All or nothing", partial: "Per blank" };

export function FillInEditor({ blanks, scoring, onBlanksChange, onScoringChange }: {
  blanks: FillInBlank[];
  scoring: ScoringMode;
  onBlanksChange: (blanks: FillInBlank[]) => void;
  onScoringChange: (scoring: ScoringMode) => void;
}) {
  const setBlank = (index: number, patch: Partial<FillInBlank>) => onBlanksChange(blanks.map((blank, i) => (i === index ? { ...blank, ...patch } : blank)));

  return (
    <Field label="Blanks" hint="One row per blank, in order. Use ___ in the question text to mark each one.">
      {() => (
        <div className="space-y-3">
          {blanks.map((blank, index) => (
            <div key={index} className="rounded-lg border border-slate-200 p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500">Blank {index + 1}</span>
                <Button variant="ghost" size="icon" aria-label="Remove blank" disabled={blanks.length <= 1} onClick={() => onBlanksChange(blanks.filter((_, i) => i !== index))}>
                  <Icon name="trash" size={14} />
                </Button>
              </div>
              <Input
                value={blank.answers.join(", ")}
                onChange={(event) => setBlank(index, { answers: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })}
                placeholder="Accepted answers, comma-separated"
              />
              <div className="mt-2 flex items-center gap-4">
                <Checkbox label="Case sensitive" checked={blank.case_sensitive ?? false} onChange={(event) => setBlank(index, { case_sensitive: event.target.checked })} />
                <Input
                  type="number"
                  value={blank.tolerance ?? ""}
                  onChange={(event) => setBlank(index, { tolerance: event.target.value ? Number(event.target.value) : undefined })}
                  placeholder="Numeric tolerance"
                  className="w-40"
                />
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between">
            <Button variant="secondary" size="sm" icon="plus" disabled={blanks.length >= 10} onClick={() => onBlanksChange([...blanks, { answers: [] }])}>
              Add blank
            </Button>
            {blanks.length > 1 && <Select aria-label="Scoring" className="w-40" value={scoring} options={toOptions(SCORING_LABELS)} onChange={(event) => onScoringChange(event.target.value as ScoringMode)} />}
          </div>
        </div>
      )}
    </Field>
  );
}
