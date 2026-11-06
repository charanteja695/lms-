import { get, useFormContext, useWatch } from "react-hook-form";

import { organizationOptionsHook } from "@/modules/user-management/common/hooks/useEntityOptions";
import { ORGANIZATION_LABELS } from "@/modules/user-management/common/labels";
import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { EntityPicker } from "@/shared/ui";

/** Institution or employer, depending on the chosen role. The server says which, and whether it is fixed. */
export function OrganizationField({ options }: { options: UserFormOptions }) {
  const { setValue, control, formState } = useFormContext<UserFormValues>();
  const [id, label] = useWatch({ control, name: ["organization_id", "organization_label"] });
  const words = ORGANIZATION_LABELS[options.organization.type ?? "institution"];

  if (!options.organization.selectable) {
    return (
      <div className="space-y-1.5">
        <p className="text-sm font-medium text-slate-700">{words.one}</p>
        <p className="flex h-10 items-center text-sm text-slate-600">{label || "Yours"}</p>
      </div>
    );
  }

  return (
    <EntityPicker
      label={words.one}
      required={options.organization.required}
      value={id}
      selectedLabel={label}
      useOptions={organizationOptionsHook(options.organization.type)}
      error={get(formState.errors, "organization_id")?.message}
      onChange={(value, text) => {
        setValue("organization_id", value, { shouldDirty: true, shouldValidate: true });
        setValue("organization_label", text);
        setValue("manager_user_id", "");
        setValue("manager_label", "");
      }}
    />
  );
}
