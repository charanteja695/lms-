import { useEffect } from "react";
import { useFormContext, useWatch } from "react-hook-form";

import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { CheckboxField, PasswordField } from "@/shared/form";
import { Alert } from "@/shared/ui";

export function PasswordChoice({ options }: { options: UserFormOptions }) {
  const { control, setValue } = useFormContext<UserFormValues>();
  const setPassword = useWatch({ control, name: "account.set_password" });
  const generatePassword = useWatch({ control, name: "account.generate_password" });
  const email = useWatch({ control, name: "account.email" });
  const hasEmail = Boolean(email && email.trim());

  useEffect(() => {
    if (setPassword) {
      setValue("account.generate_password", false);
    }
  }, [setPassword, setValue]);

  useEffect(() => {
    if (generatePassword) {
      setValue("account.set_password", false);
      setValue("account.password", "");
    }
  }, [generatePassword, setValue]);

  return (
    <div className="space-y-3 sm:col-span-2">
      {!hasEmail ? (
        <Alert tone="info">
          This user has no email address. The backend will automatically generate a secure temporary password and display it for copying after creation.
        </Alert>
      ) : (
        <div className="space-y-2">
          <CheckboxField<UserFormValues>
            name="account.generate_password"
            label="Auto-generate temporary password"
            hint="Generate a temporary password and display it immediately so you can copy and share it directly."
          />
        </div>
      )}

      <CheckboxField<UserFormValues>
        name="account.set_password"
        label="Set custom initial password"
        hint={
          hasEmail && !generatePassword
            ? "When unchecked, the user receives an email link to choose their own password (recommended)."
            : "Specify an initial password directly."
        }
      />

      {setPassword && (
        <PasswordField<UserFormValues>
          name="account.password"
          label="Initial password"
          autoComplete="new-password"
          hint={`At least ${options.initial_password.min_length} characters. The user must change it at first sign-in.`}
          required
        />
      )}
    </div>
  );
}
