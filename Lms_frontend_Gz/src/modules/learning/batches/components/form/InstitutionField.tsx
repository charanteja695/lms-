import { get, useFormContext, useWatch } from "react-hook-form";

import { useInstitutionOptions } from "@/modules/user-management/common/hooks/useEntityOptions";
import type { BatchFormValues } from "@/modules/learning/batches/form/batchForm";
import { EntityPicker } from "@/shared/ui";

/** Only rendered for accounts.manage admins, who may start a batch for any institution. */
export function InstitutionField() {
  const { control, setValue, formState } = useFormContext<BatchFormValues>();
  const [id, label] = useWatch({ control, name: ["organization_id", "organization_label"] });
  return (
    <EntityPicker
      label="Institution"
      required
      clearable={false}
      value={id}
      selectedLabel={label}
      useOptions={useInstitutionOptions}
      error={get(formState.errors, "organization_id")?.message}
      onChange={(value, text) => {
        setValue("organization_id", value, { shouldDirty: true, shouldValidate: true });
        setValue("organization_label", text);
      }}
    />
  );
}
