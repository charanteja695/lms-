import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import { useResetPasswordMutation } from "@/modules/user-management/auth/api/authApi";
import { PasswordField } from "@/shared/form";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Alert, Button } from "@/shared/ui";


export interface NewPasswordValues {
  new_password: string;
  confirm_password: string;
}

/** Shared by forgot-password, emailed reset links and account set-up links. */
export function NewPasswordForm({ resetToken, title, description, onInvalidToken }: {
  resetToken: string;
  title: string;
  description?: string;
  onInvalidToken?: () => void;
}) {
  const [resetPassword, { isLoading }] = useResetPasswordMutation();
  const navigate = useNavigate();
  const notify = useNotify();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<NewPasswordValues>({ defaultValues: { new_password: "", confirm_password: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      await resetPassword({ reset_token: resetToken, ...values }).unwrap();
      notify.success("Password updated", "Sign in with your new password.");
      navigate("/login", { replace: true });
    } catch (error) {
      const apiError = toApiError(error);
      if (apiError.code === "INVALID_RESET_TOKEN" && onInvalidToken) {
        notify.error("This link or code has expired", "Request a new one.");
        onInvalidToken();
        return;
      }
      const unmatched = applyServerErrors(apiError, form.setError, (field) => field in values);
      if (unmatched.length || !apiError.details.length) setFormError(apiError.message);
    }
  });

  return (
    <AuthCard title={title} description={description ?? "Use at least 12 characters with upper and lower case letters, a digit and a symbol."}>
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {formError && <Alert tone="error">{formError}</Alert>}
          <PasswordField<NewPasswordValues> name="new_password" label="New password" autoComplete="new-password" required />
          <PasswordField<NewPasswordValues> name="confirm_password" label="Confirm new password" autoComplete="new-password" required />
          <Button type="submit" fullWidth size="lg" loading={isLoading}>
            Save password
          </Button>
        </form>
      </FormProvider>
    </AuthCard>
  );
}
