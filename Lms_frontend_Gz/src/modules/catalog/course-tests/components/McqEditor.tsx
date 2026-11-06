import { useState } from "react";

import { toApiError } from "@/core/lib/apiError";
import { cn } from "@/core/lib/cn";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import { Alert, Button, Field, Icon, Input, Textarea } from "@/shared/ui";

const LETTERS = ["A", "B", "C", "D", "E", "F"] as const;
const MAX_OPTIONS = LETTERS.length;
const idAt = (index: number) => (LETTERS[index] ?? "A").toLowerCase();
const letterAt = (index: number) => LETTERS[index] ?? "?";

export function emptyMcq(): McqDraft {
  return { text: "", options: [0, 1, 2, 3].map((i) => ({ id: idAt(i), text: "" })), correct: "a", explanation: "", marks: 1 };
}

/** Write one multiple-choice question: the question, 2–6 options, which one is right, and why. */
export function McqEditor({ initial, number, onSave, onCancel }: { initial: McqDraft; number: number; onSave: (draft: McqDraft) => Promise<unknown>; onCancel: () => void }) {
  const [draft, setDraft] = useState<McqDraft>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (changes: Partial<McqDraft>) => setDraft((current) => ({ ...current, ...changes }));
  const setOption = (id: string, text: string) => set({ options: draft.options.map((option) => (option.id === id ? { ...option, text } : option)) });
  const addOption = () => set({ options: [...draft.options, { id: idAt(draft.options.length), text: "" }] });
  const removeOption = (id: string) => {
    // options are re-lettered a, b, c…; the correct one keeps its place among those that remain
    const kept = draft.options.filter((option) => option.id !== id);
    const correctIndex = kept.findIndex((option) => option.id === draft.correct);
    set({ options: kept.map((option, i) => ({ ...option, id: idAt(i) })), correct: idAt(Math.max(0, correctIndex)) });
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave({ ...draft, text: draft.text.trim(), options: draft.options.map((option) => ({ ...option, text: option.text.trim() })) });
    } catch (caught) {
      const apiError = toApiError(caught);
      setError(apiError.details.length ? apiError.details.map((detail) => detail.message).join(" ") : apiError.message);
    } finally {
      setSaving(false);
    }
  };
  const incomplete = !draft.text.trim() || draft.options.some((option) => !option.text.trim());

  return (
    <section className="space-y-5 rounded-2xl bg-white p-6 shadow-card ring-1 ring-slate-200/60">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-extrabold text-navy-950">Question {number} · Multiple choice</h2>
        <Field label="Marks" className="w-24">
          {(props) => <Input {...props} type="number" min={0.5} step={0.5} value={draft.marks} onChange={(event) => set({ marks: Number(event.target.value) || 1 })} />}
        </Field>
      </div>
      {error && <Alert tone="error">{error}</Alert>}
      <Field label="Question" required>
        {(props) => <Textarea {...props} rows={3} value={draft.text} placeholder="e.g. What does type(3.0) return?" onChange={(event) => set({ text: event.target.value })} />}
      </Field>

      <fieldset className="space-y-2">
        <legend className="mb-2 text-sm font-semibold text-slate-800">Options <span className="font-normal text-slate-500">· choose the correct one</span></legend>
        {draft.options.map((option, index) => {
          const correct = draft.correct === option.id;
          return (
            <div key={option.id} className={cn("flex items-center gap-2.5 rounded-xl p-2", correct ? "bg-brand-50 ring-1 ring-brand-200" : "")}>
              <input
                type="radio"
                name="correct-option"
                checked={correct}
                onChange={() => set({ correct: option.id })}
                aria-label={`Option ${letterAt(index)} is correct`}
                className="h-5 w-5 shrink-0"
              />
              <span className="w-5 text-sm font-extrabold text-slate-500">{letterAt(index)}</span>
              <Input value={option.text} aria-label={`Option ${letterAt(index)}`} onChange={(event) => setOption(option.id, event.target.value)} className="flex-1" />
              {correct && <span className="hidden text-xs font-extrabold text-brand-700 sm:inline">Correct</span>}
              {draft.options.length > 2 && (
                <Button variant="ghost" size="icon" onClick={() => removeOption(option.id)} aria-label={`Remove option ${letterAt(index)}`}>
                  <Icon name="x" size={16} />
                </Button>
              )}
            </div>
          );
        })}
        {draft.options.length < MAX_OPTIONS && (
          <Button variant="ghost" size="sm" icon="plus" onClick={addOption}>Add option</Button>
        )}
      </fieldset>

      <Field label="Explanation" hint="Shown to the learner after they submit.">
        {(props) => <Textarea {...props} rows={2} value={draft.explanation} onChange={(event) => set({ explanation: event.target.value })} />}
      </Field>

      <div className="flex flex-col-reverse gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button onClick={() => void save()} loading={saving} disabled={incomplete}>{draft.questionId ? "Save question" : "Add question"}</Button>
      </div>
    </section>
  );
}
