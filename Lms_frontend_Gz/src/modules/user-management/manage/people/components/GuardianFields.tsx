import { useFieldArray, useFormContext } from "react-hook-form";

import { toOptions } from "@/core/lib/options";
import { RELATIONSHIP_LABELS } from "@/modules/user-management/common/labels";
import { FormGrid } from "@/modules/user-management/manage/common/components/FormGrid";
import { emptyGuardian } from "@/modules/user-management/users/form/userFormDefaults";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { SelectField, TextField } from "@/shared/form";
import { Button, Icon } from "@/shared/ui";

/** A parent or guardian: the server requires one for students under `requiredBelowAge`. */
export function GuardianFields({ requiredBelowAge, max }: { requiredBelowAge: number; max: number }) {
  const { control } = useFormContext<UserFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: "student.guardians" });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-xs font-bold uppercase tracking-[0.08em] text-slate-500">Parent or guardian</h3>
          <p className="mt-0.5 text-[13px] text-slate-500">Needed for students under {requiredBelowAge}.</p>
        </div>
        {fields.length < max && (
          <Button variant="secondary" size="sm" icon="plus" onClick={() => append(emptyGuardian(fields.length === 0))}>
            Add parent or guardian
          </Button>
        )}
      </div>
      {fields.map((field, index) => (
        <div key={field.id} className="relative rounded-xl border border-slate-200 p-4 pr-14">
          <Button variant="ghost" size="icon" className="absolute right-2 top-2" onClick={() => remove(index)} aria-label={`Remove parent or guardian ${index + 1}`}>
            <Icon name="trash" size={16} />
          </Button>
          <FormGrid>
            <TextField<UserFormValues> name={`student.guardians.${index}.full_name`} label="Full name" required />
            <SelectField<UserFormValues> name={`student.guardians.${index}.relationship`} label="Relationship" options={toOptions(RELATIONSHIP_LABELS)} placeholder="Choose…" required />
            <TextField<UserFormValues> name={`student.guardians.${index}.phone`} label="Phone" type="tel" placeholder="+919876543210" required />
            <TextField<UserFormValues> name={`student.guardians.${index}.email`} label="Email" type="email" />
          </FormGrid>
        </div>
      ))}
    </div>
  );
}
