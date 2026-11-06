import { get, useFormContext, useWatch } from "react-hook-form";

import { adminOptionsHook } from "@/modules/user-management/common/hooks/useEntityOptions";
import type { InstitutionFormValues } from "@/modules/user-management/institutions/form/institutionFormValues";
import { EntityPicker } from "@/shared/ui";

const useInstitutionAdminOptions = adminOptionsHook("institution");

export function AdminField() {
  const { control, setValue, formState } = useFormContext<InstitutionFormValues>();
  const [id, label] = useWatch({ control, name: ["admin_user_id", "admin_label"] });
  return (
    <EntityPicker
      label="Owning admin"
      required
      clearable={false}
      value={id}
      selectedLabel={label}
      useOptions={useInstitutionAdminOptions}
      error={get(formState.errors, "admin_user_id")?.message}
      onChange={(value, text) => {
        setValue("admin_user_id", value, { shouldDirty: true, shouldValidate: true });
        setValue("admin_label", text);
      }}
    />
  );
}
