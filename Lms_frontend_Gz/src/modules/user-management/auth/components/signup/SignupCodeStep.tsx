import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { useRegisterMutation, useRegisterVerifyMutation } from "@/modules/user-management/auth/api/authApi";
import type { SignupValues } from "@/modules/user-management/auth/components/signup/SignupDetailsStep";
import type { LoginResponse } from "@/modules/user-management/auth/types";
import { TextField } from "@/shared/form";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Alert, Button } from "@/shared/ui";

/** Step 2: the 6-digit code from the email. A correct code creates the account and signs them in. */
export function SignupCodeStep({ values, expiresIn, onDone, onBack }: { values: SignupValues; expiresIn: number; onDone: (response: LoginResponse) => void; onBack: () => void }) {
  const notify = useNotify();
  const [verify, { isLoading }] = useRegisterVerifyMutation();
  const [resend, { isLoading: resending }] = useRegisterMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<{ code: string }>({ defaultValues: { code: "" } });

  const onSubmit = form.handleSubmit(async ({ code }) => {
    setFormError(null);
    try {
      onDone(await verify({ email: values.email, code: code.trim() }).unwrap());
    } catch (error) {
      setFormError(toApiError(error).message);
      form.reset();
    }
  });

  const sendAgain = async () => {
    try {
      await resend({ first_name: values.first_name, last_name: values.last_name, email: values.email, password: values.password }).unwrap();
      notify.info("A new code is on its way");
    } catch (error) {
      notify.apiError(error, "Could not send a new code");
    }
  };

  return (
    <AuthCard
      title="Check your email"
      description={`We sent a 6-digit code to ${values.email}. It expires in ${Math.round(expiresIn / 60)} minutes.`}
      footer={
        <div className="flex justify-center gap-4">
          <button type="button" onClick={onBack} className="font-medium text-brand-700 hover:underline">Change details</button>
          <button type="button" disabled={resending} onClick={() => void sendAgain()} className="font-medium text-brand-700 hover:underline disabled:opacity-50">Send a new code</button>
        </div>
      }
    >
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {formError && <Alert tone="error">{formError}</Alert>}
          <TextField name="code" label="Code" inputMode="numeric" autoComplete="one-time-code" maxLength={10} placeholder="6-digit code" required />
          <Button type="submit" fullWidth size="lg" loading={isLoading}>Create account</Button>
        </form>
      </FormProvider>
    </AuthCard>
  );
}
