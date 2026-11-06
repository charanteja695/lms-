import { useFormContext, useWatch } from "react-hook-form";

import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { CheckboxField, FormSection, TextField } from "@/shared/form";

export function AddressSection() {
  const { control } = useFormContext<UserFormValues>();
  const include = useWatch({ control, name: "include_address" });
  return (
    <FormSection title="Address" actions={<CheckboxField<UserFormValues> name="include_address" label="Add address" />}>
      {include ? (
        <>
          <TextField<UserFormValues> name="address.line1" label="Address line 1" required className="sm:col-span-2" />
          <TextField<UserFormValues> name="address.line2" label="Address line 2" className="sm:col-span-2" />
          <TextField<UserFormValues> name="address.city" label="City" required />
          <TextField<UserFormValues> name="address.state" label="State" required />
          <TextField<UserFormValues> name="address.postal_code" label="Postal code" required />
          <TextField<UserFormValues> name="address.country" label="Country code" maxLength={2} hint="e.g. IN" required />
        </>
      ) : (
        <p className="text-sm text-slate-500 sm:col-span-2">No address recorded.</p>
      )}
    </FormSection>
  );
}
