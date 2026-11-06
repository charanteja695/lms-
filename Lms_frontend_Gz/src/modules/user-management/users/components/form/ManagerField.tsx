import { useMemo } from "react";
import { get, useFormContext, useWatch } from "react-hook-form";

import { managerOptionsHook } from "@/modules/user-management/common/hooks/useEntityOptions";
import { ROLE_LABELS } from "@/modules/user-management/common/labels";
import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { EntityPicker } from "@/shared/ui";

export function ManagerField({ options }: { options: UserFormOptions }) {
  const { setValue, control, formState } = useFormContext<UserFormValues>();
  const [organizationId, id, label] = useWatch({ control, name: ["organization_id", "manager_user_id", "manager_label"] });
  const managerRole = options.manager.role;
  const useOptions = useMemo(() => managerOptionsHook(managerRole, organizationId), [managerRole, organizationId]);

  return (
    <EntityPicker
      label="Reports to"
      hint={options.manager.defaults_to_you ? "Optional. Defaults to you." : `Optional. ${managerRole ? ROLE_LABELS[managerRole] : ""}`}
      value={id}
      selectedLabel={label}
      disabled={!options.organization.fixed && !organizationId}
      useOptions={useOptions}
      error={get(formState.errors, "manager_user_id")?.message}
      onChange={(value, text) => {
        setValue("manager_user_id", value, { shouldDirty: true });
        setValue("manager_label", text);
      }}
    />
  );
}
