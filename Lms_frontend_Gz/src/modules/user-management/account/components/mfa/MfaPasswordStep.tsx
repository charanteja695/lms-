import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { toApiError } from "@/core/lib/apiError";
import { useStartMfaSetupMutation } from "@/modules/user-management/auth/api/authApi";
import { PasswordField } from "@/shared/form";
import { Alert, Button } from "@/shared/ui";

export function PasswordStep({ onStarted }: { onStarted: (secret: string, uri: string) => void }) {
  const [start, { isLoading }] = useStartMfaSetupMutation();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<{ password: string }>({
    defaultValues: { password: "" },
  });
  const onSubmit = form.handleSubmit(async ({ password }) => {
    setError(null);
    try {
      const setup = await start({ password }).unwrap();
      onStarted(setup.secret, setup.otpauth_uri);
    } catch (caught) {
      setError(toApiError(caught).message);
    }
  });
  return (
    <FormProvider {...form}>
      <form onSubmit={onSubmit} className="max-w-md space-y-4" noValidate>
        <p className="text-sm text-slate-600">Confirm your password to start. You will need an authenticator app such as Google Authenticator or Microsoft Authenticator.</p>
        {error && <Alert tone="error">{error}</Alert>}
        <PasswordField name="password" label="Current password" required />
        <Button type="submit" loading={isLoading}>
          Continue
        </Button>
      </form>
    </FormProvider>
  );
}
