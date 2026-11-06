import { FormProvider, useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { useAppDispatch } from "@/app/hooks";
import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import { useChangePasswordMutation } from "@/modules/user-management/auth/api/authApi";
import { loggedOut } from "@/modules/user-management/auth/store/authSlice";
import { PasswordField } from "@/shared/form";
import { Button } from "@/shared/ui";

interface Values {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

/** The server ends every session after a password change, so the user signs in again afterwards. */
export function ChangePasswordForm({ submitLabel = "Change password" }: { submitLabel?: string }) {
  const [changePassword, { isLoading }] = useChangePasswordMutation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const notify = useNotify();
  const form = useForm<Values>({ defaultValues: { current_password: "", new_password: "", confirm_password: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await changePassword(values).unwrap();
      notify.success("Password changed", "Sign in again with your new password.");
      dispatch(loggedOut());
      navigate("/login", { replace: true });
    } catch (error) {
      const apiError = toApiError(error);
      const unmatched = applyServerErrors(apiError, form.setError, (field) => field in values);
      if (unmatched.length || !apiError.details.length) notify.apiError(error, "Password not changed");
    }
  });

  return (
    <FormProvider {...form}>
      <form onSubmit={onSubmit} className="max-w-md space-y-4" noValidate>
        <PasswordField<Values> name="current_password" label="Current password" required />
        <PasswordField<Values>
          name="new_password"
          label="New password"
          autoComplete="new-password"
          hint="At least 12 characters with upper and lower case letters, a digit and a symbol."
          required
        />
        <PasswordField<Values> name="confirm_password" label="Confirm new password" autoComplete="new-password" required />
        <Button type="submit" loading={isLoading}>
          {submitLabel}
        </Button>
      </form>
    </FormProvider>
  );
}
