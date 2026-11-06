import { newOptionId } from "@/modules/assessments/questions/lib/ids";
import type { RubricCriterion } from "@/modules/assessments/questions/bodyTypes";
import { Button, Field, Icon, Input } from "@/shared/ui";

/** Shared by subjective and file_submission questions: the criteria a grader scores against. */
export function RubricEditor({ rubric, onChange }: { rubric: RubricCriterion[]; onChange: (rubric: RubricCriterion[]) => void }) {
  return (
    <Field label="Rubric" hint="Optional. Leave empty to grade with a single marks field instead.">
      {() => (
        <div className="space-y-2">
          {rubric.map((criterion) => (
            <div key={criterion.id} className="flex items-center gap-2">
              <Input
                value={criterion.criterion}
                onChange={(event) => onChange(rubric.map((item) => (item.id === criterion.id ? { ...item, criterion: event.target.value } : item)))}
                placeholder="Criterion"
                className="flex-1"
              />
              <Input
                type="number"
                value={criterion.max_marks}
                onChange={(event) => onChange(rubric.map((item) => (item.id === criterion.id ? { ...item, max_marks: Number(event.target.value) } : item)))}
                placeholder="Max marks"
                className="w-28"
              />
              <Button variant="ghost" size="icon" aria-label="Remove criterion" onClick={() => onChange(rubric.filter((item) => item.id !== criterion.id))}>
                <Icon name="trash" size={14} />
              </Button>
            </div>
          ))}
          <Button variant="secondary" size="sm" icon="plus" onClick={() => onChange([...rubric, { id: newOptionId(), criterion: "", max_marks: 5 }])}>
            Add criterion
          </Button>
        </div>
      )}
    </Field>
  );
}
