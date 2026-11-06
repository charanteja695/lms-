import { RubricEditor } from "@/modules/assessments/questions/components/editors/RubricEditor";
import type { RubricCriterion } from "@/modules/assessments/questions/bodyTypes";
import { Field, Input } from "@/shared/ui";

export function FileSubmissionEditor({ allowedExtensions, maxFiles, maxSizeMb, rubric, onAllowedExtensionsChange, onMaxFilesChange, onMaxSizeMbChange, onRubricChange }: {
  allowedExtensions: string;
  maxFiles: string;
  maxSizeMb: string;
  rubric: RubricCriterion[];
  onAllowedExtensionsChange: (value: string) => void;
  onMaxFilesChange: (value: string) => void;
  onMaxSizeMbChange: (value: string) => void;
  onRubricChange: (rubric: RubricCriterion[]) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Allowed extensions" hint="Comma-separated, e.g. pdf, zip">
          {(props) => <Input {...props} value={allowedExtensions} onChange={(event) => onAllowedExtensionsChange(event.target.value)} />}
        </Field>
        <Field label="Max files" required>
          {(props) => <Input {...props} type="number" value={maxFiles} onChange={(event) => onMaxFilesChange(event.target.value)} />}
        </Field>
        <Field label="Max size (MB)" required>
          {(props) => <Input {...props} type="number" value={maxSizeMb} onChange={(event) => onMaxSizeMbChange(event.target.value)} />}
        </Field>
      </div>
      <RubricEditor rubric={rubric} onChange={onRubricChange} />
    </div>
  );
}
