import { useEffect, useRef } from "react";
import { useFormContext, useWatch } from "react-hook-form";

import { ADMIN_SCOPE_LABELS } from "@/modules/user-management/common/labels";
import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { Checkbox } from "@/shared/ui";

/** What an admin is responsible for. The options and the defaults come from the server. */
export function ScopesField({ options }: { options: UserFormOptions["scopes"] }) {
  const { control, setValue } = useFormContext<UserFormValues>();
  const selected = useWatch({ control, name: "scopes" }) ?? [];
  const applied = useRef(false);

  useEffect(() => {
    // Pre-select the server's defaults once, when creating.
    if (applied.current || selected.length > 0 || options.default.length === 0) return;
    applied.current = true;
    setValue("scopes", options.default, { shouldDirty: false });
  }, [options.default, selected.length, setValue]);

  const toggle = (scope: string, checked: boolean) => {
    const next = checked ? [...selected, scope] : selected.filter((value) => value !== scope);
    setValue("scopes", next, { shouldDirty: true });
  };

  return (
    <div className="space-y-2 sm:col-span-2">
      <p className="text-sm font-medium text-slate-700">Responsibilities</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.options.map((scope) => (
          <Checkbox
            key={scope}
            label={ADMIN_SCOPE_LABELS[scope]}
            description={scope}
            checked={selected.includes(scope)}
            onChange={(event) => toggle(scope, event.target.checked)}
          />
        ))}
      </div>
    </div>
  );
}
