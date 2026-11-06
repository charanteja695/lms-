import { toOptions } from "@/core/lib/options";
import { newOptionId } from "@/modules/assessments/questions/lib/ids";
import type { ChoiceOption, McqMultiAnswerKey, McqSingleAnswerKey, ScoringMode } from "@/modules/assessments/questions/bodyTypes";
import { Button, Checkbox, Field, Icon, Input, Select } from "@/shared/ui";

const SCORING_LABELS: Record<ScoringMode, string> = { all_or_nothing: "All or nothing", partial: "Partial credit" };

/** Shared editor for mcq_single (radio) and mcq_multi (checkboxes + scoring mode). */
export function ChoiceEditor({ multi, options, correct, scoring, onOptionsChange, onCorrectChange, onScoringChange }: {
  multi: boolean;
  options: ChoiceOption[];
  correct: string[];
  scoring: ScoringMode;
  onOptionsChange: (options: ChoiceOption[]) => void;
  onCorrectChange: (correct: string[]) => void;
  onScoringChange: (scoring: ScoringMode) => void;
}) {
  const setOption = (id: string, text: string) => onOptionsChange(options.map((option) => (option.id === id ? { ...option, text } : option)));
  const removeOption = (id: string) => {
    onOptionsChange(options.filter((option) => option.id !== id));
    onCorrectChange(correct.filter((value) => value !== id));
  };
  const toggleCorrect = (id: string) => {
    if (multi) onCorrectChange(correct.includes(id) ? correct.filter((value) => value !== id) : [...correct, id]);
    else onCorrectChange([id]);
  };

  return (
    <Field label="Options" hint="Mark the correct answer(s). 2–12 options.">
      {() => (
        <div className="space-y-2">
          {options.map((option) => (
            <div key={option.id} className="flex items-center gap-2">
              {multi ? (
                <Checkbox label="" checked={correct.includes(option.id)} onChange={() => toggleCorrect(option.id)} />
              ) : (
                <input type="radio" checked={correct.includes(option.id)} onChange={() => toggleCorrect(option.id)} className="h-4 w-4 text-brand-600 focus:ring-brand-500" />
              )}
              <Input value={option.text} onChange={(event) => setOption(option.id, event.target.value)} placeholder="Option text" className="flex-1" />
              <Button variant="ghost" size="icon" aria-label="Remove option" disabled={options.length <= 2} onClick={() => removeOption(option.id)}>
                <Icon name="trash" size={14} />
              </Button>
            </div>
          ))}
          <div className="flex items-center justify-between">
            <Button variant="secondary" size="sm" icon="plus" disabled={options.length >= 12} onClick={() => onOptionsChange([...options, { id: newOptionId(), text: "" }])}>
              Add option
            </Button>
            {multi && <Select aria-label="Scoring" className="w-48" value={scoring} options={toOptions(SCORING_LABELS)} onChange={(event) => onScoringChange(event.target.value as ScoringMode)} />}
          </div>
        </div>
      )}
    </Field>
  );
}

export function emptyChoiceState(): { options: ChoiceOption[]; correct: string[]; scoring: ScoringMode } {
  const a = newOptionId();
  const b = newOptionId();
  return { options: [{ id: a, text: "" }, { id: b, text: "" }], correct: [], scoring: "all_or_nothing" };
}

export function toChoiceBody(options: ChoiceOption[]) {
  return { options };
}

export function toSingleAnswerKey(correct: string[]): McqSingleAnswerKey {
  return { correct: correct[0] ?? "" };
}

export function toMultiAnswerKey(correct: string[], scoring: ScoringMode): McqMultiAnswerKey {
  return { correct, scoring };
}
