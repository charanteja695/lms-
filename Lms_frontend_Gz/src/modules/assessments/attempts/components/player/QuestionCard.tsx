import { useState } from "react";

import { AnswerRenderer } from "@/modules/assessments/attempts/components/player/answers/AnswerRenderer";
import type { PaperQuestion } from "@/modules/assessments/attempts/paperTypes";
import { Card, Checkbox, Spinner } from "@/shared/ui";

export function QuestionCard({ attemptId, question, index, onSave, isSaving, disabled }: {
  attemptId: string;
  question: PaperQuestion;
  index: number;
  onSave: (questionId: string, response: Record<string, unknown> | null, flagged?: boolean) => void;
  isSaving: boolean;
  disabled: boolean;
}) {
  const [response, setResponse] = useState<Record<string, unknown> | null>(question.answer);
  const [flagged, setFlagged] = useState(false);

  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <span className="text-slate-400">Q{index + 1}</span>
          <span className="font-normal text-slate-500">({question.marks} {question.marks === 1 ? "mark" : "marks"})</span>
        </span>
      }
      actions={
        <span className="flex items-center gap-2">
          {isSaving && <Spinner size={14} className="text-slate-400" />}
          <Checkbox
            label="Flag for review"
            checked={flagged}
            disabled={disabled}
            onChange={(event) => {
              setFlagged(event.target.checked);
              onSave(question.question_id, response, event.target.checked);
            }}
          />
        </span>
      }
    >
      <p className="mb-4 whitespace-pre-wrap text-sm text-slate-800">{question.text}</p>
      <AnswerRenderer
        attemptId={attemptId}
        question={question}
        response={response}
        disabled={disabled}
        onChange={(next) => {
          setResponse(next);
          onSave(question.question_id, next, flagged);
        }}
      />
    </Card>
  );
}
