import { get, useFieldArray, useFormContext, useWatch } from "react-hook-form";

import { toOptions } from "@/core/lib/options";
import { RELATIONSHIP_LABELS } from "@/modules/user-management/common/labels";
import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import { emptyGuardian } from "@/modules/user-management/users/form/userFormDefaults";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { FormSection, SelectField, TextField } from "@/shared/form";
import { Alert, Button, Icon } from "@/shared/ui";

export function StudentSection({ options }: { options: UserFormOptions }) {
  const { control, formState, setValue } = useFormContext<UserFormValues>();
  const { fields, append, remove } = useFieldArray({ control, name: "student.guardians" });
  const guardians = useWatch({ control, name: "student.guardians" });
  const listError = get(formState.errors, "student.guardians")?.message as string | undefined;
  const maxGuardians = options.guardians.max;

  return (
    <>
      <FormSection title="Student details" description="Admission numbers are unique in the institution and never reused.">
        <TextField<UserFormValues> name="student.admission_number" label="Admission number" placeholder="ADM/2024/0457" required />
        <TextField<UserFormValues> name="student.admission_date" label="Admission date" type="date" />
      </FormSection>

      <FormSection title="Academic placement" description="Used for batches, reports and job eligibility." columns={3}>
        <TextField<UserFormValues> name="student.program" label="Program" placeholder="B.Tech" />
        <TextField<UserFormValues> name="student.branch" label="Branch" placeholder="Computer Science" />
        <TextField<UserFormValues> name="student.year_of_study" label="Year of study" type="number" placeholder="3" />
        <TextField<UserFormValues> name="student.section" label="Section" placeholder="A" />
        <TextField<UserFormValues> name="student.graduation_year" label="Graduation year" type="number" placeholder="2027" />
        <TextField<UserFormValues> name="student.cgpa" label="CGPA" placeholder="8.45" />
      </FormSection>

      {options.sections.guardians && (
        <FormSection
          title="Guardians"
          description={`Required for students under ${options.guardians.required_below_age}. Up to ${maxGuardians}.`}
          columns={1}
          actions={
            fields.length < maxGuardians && (
              <Button variant="secondary" size="sm" icon="plus" onClick={() => append(emptyGuardian(fields.length === 0))}>
                Add guardian
              </Button>
            )
          }
        >
          {listError && <Alert tone="error">{listError}</Alert>}
          {fields.length === 0 && <p className="text-sm text-slate-500">No guardians added.</p>}
          {fields.map((field, index) => (
            <div key={field.id} className="rounded-lg border border-slate-200 p-4">
              <div className="mb-3 flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="radio"
                    name="primary-guardian"
                    checked={Boolean(guardians?.[index]?.is_primary)}
                    onChange={() => guardians?.forEach((_, i) => setValue(`student.guardians.${i}.is_primary`, i === index, { shouldDirty: true }))}
                    className="h-4 w-4 border-slate-300 text-brand-600"
                  />
                  Primary contact
                </label>
                <Button variant="ghost" size="sm" onClick={() => remove(index)} aria-label={`Remove guardian ${index + 1}`}>
                  <Icon name="trash" size={16} />
                </Button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <TextField<UserFormValues> name={`student.guardians.${index}.full_name`} label="Full name" required />
                <SelectField<UserFormValues> name={`student.guardians.${index}.relationship`} label="Relationship" options={toOptions(RELATIONSHIP_LABELS)} placeholder="Select" required />
                <TextField<UserFormValues> name={`student.guardians.${index}.phone`} label="Phone" type="tel" required />
                <TextField<UserFormValues> name={`student.guardians.${index}.email`} label="Email" type="email" />
                <TextField<UserFormValues> name={`student.guardians.${index}.occupation`} label="Occupation" />
              </div>
            </div>
          ))}
        </FormSection>
      )}
    </>
  );
}
