import { useFieldArray, useFormContext } from "react-hook-form";

import type { TemplateFormValues } from "@/modules/certificates/templates/form/templateForm";
import { TextField } from "@/shared/form";
import { Button, Icon } from "@/shared/ui";

const MAX_SIGNATORIES = 3;

export function SignatoriesEditor() {
  const { control } = useFormContext<TemplateFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: "signatories" });

  return (
    <div className="space-y-3 sm:col-span-2">
      {fields.length === 0 && <p className="text-sm text-slate-500">No signatories — the certificate is signed by the issuer only.</p>}
      {fields.map((field, index) => (
        <div key={field.id} className="flex items-end gap-3">
          <TextField<TemplateFormValues> name={`signatories.${index}.name`} label="Name" required maxLength={80} className="flex-1" />
          <TextField<TemplateFormValues> name={`signatories.${index}.title`} label="Title" maxLength={80} placeholder="Director" className="flex-1" />
          <Button variant="ghost" size="icon" aria-label="Remove signatory" onClick={() => remove(index)}>
            <Icon name="trash" size={16} />
          </Button>
        </div>
      ))}
      {fields.length < MAX_SIGNATORIES && (
        <Button variant="secondary" size="sm" icon="plus" onClick={() => append({ name: "", title: "" })}>
          Add signatory
        </Button>
      )}
    </div>
  );
}
