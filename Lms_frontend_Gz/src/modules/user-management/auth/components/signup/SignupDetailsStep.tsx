import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { toApiError } from "@/core/lib/apiError";
import { useRegisterMutation } from "@/modules/user-management/auth/api/authApi";
import { PasswordField, TextField } from "@/shared/form";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Alert, Button, Icon } from "@/shared/ui";

export interface SignupValues {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  confirm_password: string;
}

/** Step 1: name, email and a password. The server checks the password's strength and that the email is free. */
export function SignupDetailsStep({ initial, onSent }: { initial?: SignupValues; onSent: (values: SignupValues, expiresIn: number) => void }) {
  const [register, { isLoading }] = useRegisterMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<SignupValues>({ defaultValues: initial ?? { first_name: "", last_name: "", email: "", password: "", confirm_password: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    if (values.password !== values.confirm_password) {
      form.setError("confirm_password", { message: "The passwords do not match" });
      return;
    }
    try {
      const response = await register({ first_name: values.first_name, last_name: values.last_name, email: values.email, password: values.password }).unwrap();
      onSent(values, response.signup.expires_in);
    } catch (error) {
      const apiError = toApiError(error);
      const fields: (keyof SignupValues)[] = ["first_name", "last_name", "email", "password"];
      const onFields = apiError.details.filter((d) => fields.includes(d.field as keyof SignupValues));
      onFields.forEach((d) => form.setError(d.field as keyof SignupValues, { message: d.message }));
      if (apiError.code === "EMAIL_TAKEN") form.setError("email", { message: apiError.message });
      else if (onFields.length === 0) setFormError(apiError.message);
    }
  });

  return (
    <AuthCard
      title="Create your account"
      description="Learn at your own pace: buy a course, study it with tests and certificates, and use the AI tutor, resume builder and interview practice."
      footer={<>Already have an account? <Link to="/login" className="font-semibold text-brand-700 underline-offset-4 hover:underline">Sign in</Link></>}
    >
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField<SignupValues> name="first_name" label="First name" autoComplete="given-name" required />
            <TextField<SignupValues> name="last_name" label="Last name" autoComplete="family-name" required />
          </div>
          <TextField<SignupValues> name="email" label="Email" type="email" autoComplete="email" required />
          <PasswordField<SignupValues> name="password" label="Password" autoComplete="new-password" required />
          <PasswordField<SignupValues> name="confirm_password" label="Confirm password" autoComplete="new-password" required />
          <Button type="submit" fullWidth size="lg" loading={isLoading}>Continue</Button>
          <p className="flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <Icon name="mail" size={14} className="text-brand-600" />
            We'll email you a code to confirm it's you
          </p>
        </form>
      </FormProvider>
    </AuthCard>
  );
}
