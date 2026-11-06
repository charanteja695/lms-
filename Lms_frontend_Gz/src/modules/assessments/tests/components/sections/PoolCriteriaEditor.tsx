import { QUESTION_TYPE_LABELS } from "@/modules/assessments/common/labels";
import type { QuestionType } from "@/modules/assessments/common/types";
import type { PoolCriteria } from "@/modules/assessments/tests/sectionTypes";
import { Checkbox, Field, Input } from "@/shared/ui";

const TYPES = Object.keys(QUESTION_TYPE_LABELS) as QuestionType[];

function toList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

/** Which questions a pool slot may draw from: any-of within a kind, all given kinds must match. */
export function PoolCriteriaEditor({ criteria, onChange }: { criteria: PoolCriteria; onChange: (criteria: PoolCriteria) => void }) {
  const types = criteria.types ?? [];

  return (
    <div className="space-y-3 rounded-lg bg-slate-50 p-3">
      <Field label="Question types" hint="Leave all unchecked to allow any type.">
        {() => (
          <div className="flex flex-wrap gap-3">
            {TYPES.map((type) => (
              <Checkbox
                key={type}
                label={QUESTION_TYPE_LABELS[type]}
                checked={types.includes(type)}
                onChange={() => onChange({ ...criteria, types: types.includes(type) ? types.filter((value) => value !== type) : [...types, type] })}
              />
            ))}
          </div>
        )}
      </Field>
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Difficulty min">
          {(props) => <Input {...props} type="number" min={1} max={5} value={criteria.difficulty_min ?? ""} onChange={(event) => onChange({ ...criteria, difficulty_min: event.target.value ? Number(event.target.value) : undefined })} />}
        </Field>
        <Field label="Difficulty max">
          {(props) => <Input {...props} type="number" min={1} max={5} value={criteria.difficulty_max ?? ""} onChange={(event) => onChange({ ...criteria, difficulty_max: event.target.value ? Number(event.target.value) : undefined })} />}
        </Field>
        <Field label="Skills" hint="Comma-separated">
          {(props) => <Input {...props} value={(criteria.skills ?? []).join(", ")} onChange={(event) => onChange({ ...criteria, skills: toList(event.target.value) })} />}
        </Field>
        <Field label="Topics" hint="Comma-separated">
          {(props) => <Input {...props} value={(criteria.topics ?? []).join(", ")} onChange={(event) => onChange({ ...criteria, topics: toList(event.target.value) })} />}
        </Field>
      </div>
      <Field label="Tags" hint="Comma-separated">
        {(props) => <Input {...props} value={(criteria.tags ?? []).join(", ")} onChange={(event) => onChange({ ...criteria, tags: toList(event.target.value) })} />}
      </Field>
    </div>
  );
}
