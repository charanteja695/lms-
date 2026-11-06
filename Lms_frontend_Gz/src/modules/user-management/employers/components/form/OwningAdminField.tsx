import { get, useFormContext, useWatch } from "react-hook-form";

import { adminOptionsHook } from "@/modules/user-management/common/hooks/useEntityOptions";
import type { EmployerFormValues } from "@/modules/user-management/employers/form/employerForm";
import { EntityPicker } from "@/shared/ui";

/** Only admins with the careers.manage responsibility can own employers; the API filters the list. */
export function OwningAdminField() {
  const { control, setValue, formState } = useFormContext<EmployerFormValues>();
  const [id, label] = useWatch({ control, name: ["admin_user_id", "admin_label"] });
  return (
    <EntityPicker
      label="Owning admin"
      required
      clearable={false}
      value={id}
      selectedLabel={label}
      useOptions={adminOptionsHook("employer")}
      error={get(formState.errors, "admin_user_id")?.message}
      onChange={(value, text) => {
        setValue("admin_user_id", value, { shouldDirty: true, shouldValidate: true });
        setValue("admin_label", text);
      }}
    />
  );
}
