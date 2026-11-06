import { RubricEditor } from "@/modules/assessments/questions/components/editors/RubricEditor";
import type { RubricCriterion } from "@/modules/assessments/questions/bodyTypes";
import { Field, Input, Textarea } from "@/shared/ui";

export function SubjectiveEditor({ rubric, maxWords, modelAnswer, onRubricChange, onMaxWordsChange, onModelAnswerChange }: {
  rubric: RubricCriterion[];
  maxWords: string;
  modelAnswer: string;
  onRubricChange: (rubric: RubricCriterion[]) => void;
  onMaxWordsChange: (value: string) => void;
  onModelAnswerChange: (value: string) => void;
}) {
  return (
    <div className="space-y-4">
      <RubricEditor rubric={rubric} onChange={onRubricChange} />
      <Field label="Max words" hint="Optional.">
        {(props) => <Input {...props} type="number" value={maxWords} onChange={(event) => onMaxWordsChange(event.target.value)} className="w-40" />}
      </Field>
      <Field label="Model answer" hint="Shown to graders only, never to the student.">
        {(props) => <Textarea {...props} value={modelAnswer} onChange={(event) => onModelAnswerChange(event.target.value)} rows={4} />}
      </Field>
    </div>
  );
}
