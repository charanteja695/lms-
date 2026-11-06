import { useFieldArray, useFormContext } from "react-hook-form";

import type { TemplateFormValues } from "@/modules/certificates/templates/form/templateForm";
import { TextField } from "@/shared/form";
import { Button, Icon } from "@/shared/ui";

const MAX_BANDS = 8;

export function GradeBandsEditor() {
  const { control } = useFormContext<TemplateFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: "grade_bands" });

  return (
    <div className="space-y-3 sm:col-span-2">
      {fields.length === 0 && <p className="text-sm text-slate-500">Using the default bands: Distinction ≥ 85, Merit ≥ 70, Pass.</p>}
      {fields.map((field, index) => (
        <div key={field.id} className="flex items-end gap-3">
          <TextField<TemplateFormValues> name={`grade_bands.${index}.min_percent`} label="From %" type="number" inputMode="numeric" required className="w-28" />
          <TextField<TemplateFormValues> name={`grade_bands.${index}.label`} label="Label" required maxLength={60} placeholder="Distinction" className="flex-1" />
          <Button variant="ghost" size="icon" aria-label="Remove band" onClick={() => remove(index)}>
            <Icon name="trash" size={16} />
          </Button>
        </div>
      ))}
      {fields.length < MAX_BANDS && (
        <Button variant="secondary" size="sm" icon="plus" onClick={() => append({ min_percent: "", label: "" })}>
          Add band
        </Button>
      )}
    </div>
  );
}
