import { useState } from "react";

import { cn } from "@/core/lib/cn";
import type { ReviewQuestion } from "@/modules/assessments/attempts/resultTypes";
import { Icon } from "@/shared/ui";

type Option = { id: string; text: string };

/** The text of the chosen and the correct option, for single-choice questions; null for other kinds. */
function choiceTexts(question: ReviewQuestion): { yours: string | null; right: string | null } | null {
  const options = (question.body.options as Option[] | undefined) ?? null;
  if (!options) return null;
  const textOf = (id: unknown) => options.find((option) => option.id === id)?.text ?? null;
  return { yours: textOf(question.response?.selected), right: textOf(question.answer_key?.correct) };
}

function Row({ question, initiallyOpen }: { question: ReviewQuestion; initiallyOpen: boolean }) {
  const [open, setOpen] = useState(initiallyOpen);
  const right = question.is_correct === true || (question.marks_awarded != null && question.marks_awarded >= question.marks);
  const choices = choiceTexts(question);
  return (
    <li className="overflow-hidden rounded-2xl bg-white shadow-card ring-1 ring-slate-200/60">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left">
        <span className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white", right ? "bg-brand-600" : "bg-red-600")}>
          <Icon name={right ? "check" : "x"} size={14} />
        </span>
        <span className="min-w-0 flex-1 text-[15px] font-semibold text-slate-900">{question.position}. {question.question_type === "coding" ? "Program: " : ""}{question.text}</span>
        {question.marks_awarded != null && <span className="text-sm font-bold text-slate-600">{question.marks_awarded} / {question.marks}</span>}
      </button>
      {open && (
        <div className="space-y-2 px-4 pb-4 pl-14 text-sm text-slate-700">
          {choices && (
            <>
              <p>Your answer: <strong className={right ? "text-brand-800" : "text-red-700"}>{choices.yours ?? "Not answered"}</strong></p>
              {!right && choices.right && <p>Correct answer: <strong className="text-brand-800">{choices.right}</strong></p>}
            </>
          )}
          {question.feedback && <p>{question.feedback}</p>}
          {question.explanation && <p className="rounded-xl bg-navy-50 px-3 py-2 text-navy-900">{question.explanation}</p>}
        </div>
      )}
    </li>
  );
}

/** Each question with the learner's answer, the right one and why, wrong ones opened first. */
export function ReviewList({ questions }: { questions: ReviewQuestion[] }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-extrabold text-navy-950">Review your answers</h2>
      <ol className="space-y-2">
        {questions.map((question) => (
          <Row key={question.question_id} question={question} initiallyOpen={question.is_correct === false} />
        ))}
      </ol>
    </section>
  );
}
