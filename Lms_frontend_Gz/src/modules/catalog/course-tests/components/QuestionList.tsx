import { cn } from "@/core/lib/cn";
import { useGetQuestionQuery } from "@/modules/assessments/questions/api/questionsApi";
import type { Question } from "@/modules/assessments/questions/types";
import type { Test } from "@/modules/assessments/tests/types";
import { Button, Icon } from "@/shared/ui";

export interface PaperEntry {
  sectionIndex: number;
  slotIndex: number;
  questionId: string;
  marks: number;
}

/** The fixed questions on a test's paper, in order. */
export function paperEntries(test: Test): PaperEntry[] {
  return test.sections.flatMap((section, sectionIndex) =>
    section.slots.flatMap((slot, slotIndex) => (slot.slot_type === "fixed" && slot.question_id ? [{ sectionIndex, slotIndex, questionId: slot.question_id, marks: slot.marks }] : [])),
  );
}

function Row({ entry, number, selected, editable, onSelect, onRemove }: {
  entry: PaperEntry;
  number: number;
  selected: boolean;
  editable: boolean;
  onSelect: (question: Question) => void;
  onRemove: () => void;
}) {
  const { data: question } = useGetQuestionQuery(entry.questionId);
  const version = question?.working ?? question?.current;
  const isProgram = question?.question_type === "coding";
  return (
    <li className={cn("flex items-start gap-2 rounded-xl bg-white p-1 ring-1 transition-shadow", selected ? "ring-2 ring-brand-500" : "ring-slate-200")}>
      <button type="button" onClick={() => question && onSelect(question)} disabled={!question} className="flex min-h-12 min-w-0 flex-1 items-start gap-3 rounded-lg p-2 text-left hover:bg-slate-50">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-extrabold text-navy-950">{number}</span>
        <span className="min-w-0">
          <span className="line-clamp-2 text-sm font-semibold text-slate-900">{version?.text ?? "Loading…"}</span>
          <span className={cn("text-xs font-bold", isProgram ? "text-navy-700" : "text-brand-700")}>
            {isProgram ? "Program" : "Multiple choice"} · {entry.marks} {entry.marks === 1 ? "mark" : "marks"}
          </span>
        </span>
      </button>
      {editable && (
        <Button variant="ghost" size="icon" onClick={onRemove} aria-label={`Remove question ${number}`}>
          <Icon name="trash" size={16} />
        </Button>
      )}
    </li>
  );
}

export function QuestionList({ test, selectedId, editable, onSelect, onRemove }: {
  test: Test;
  selectedId: string | null;
  editable: boolean;
  onSelect: (question: Question) => void;
  onRemove: (entry: PaperEntry) => void;
}) {
  const entries = paperEntries(test);
  if (entries.length === 0) return <p className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">No questions yet. Add multiple-choice questions and at least one program.</p>;
  return (
    <ol className="space-y-2">
      {entries.map((entry, index) => (
        // a paper keeps at least one question, so the last one cannot be removed (add another first)
        <Row key={`${entry.sectionIndex}-${entry.slotIndex}`} entry={entry} number={index + 1} selected={selectedId === entry.questionId} editable={editable && entries.length > 1} onSelect={onSelect} onRemove={() => onRemove(entry)} />
      ))}
    </ol>
  );
}
