import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { useAppSelector } from "@/app/hooks";
import { toApiError } from "@/core/lib/apiError";
import { cleanOtp, isCompleteOtp } from "@/core/lib/otp";
import { useVerifyMfaMutation } from "@/modules/user-management/auth/api/authApi";
import type { LoginResponse } from "@/modules/user-management/auth/types";
import { TextField } from "@/shared/form";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Alert, Button } from "@/shared/ui";

interface MfaValues {
  code: string;
  recovery_code: string;
}

export function MfaStep({ onDone, onCancel }: { onDone: (response: LoginResponse) => void; onCancel: () => void }) {
  const challenge = useAppSelector((state) => state.auth.mfaChallenge);
  const [useRecovery, setUseRecovery] = useState(false);
  const [verify, { isLoading }] = useVerifyMfaMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<MfaValues>({ defaultValues: { code: "123456", recovery_code: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    if (!challenge) return;
    setFormError(null);
    const code = cleanOtp(values.code);
    if (!useRecovery && !isCompleteOtp(code)) {
      form.setError("code", { message: "Enter the 6-digit code." }); // not sent: an empty try would use up an attempt
      return;
    }
    try {
      const response = await verify(
        useRecovery
          ? { mfa_token: challenge.mfa_token, recovery_code: values.recovery_code.trim() }
          : { mfa_token: challenge.mfa_token, code },
      ).unwrap();
      onDone(response);
    } catch (error) {
      const apiError = toApiError(error);
      if (apiError.code === "INVALID_MFA_TOKEN") {
        onCancel();
        return;
      }
      setFormError(apiError.message);
      form.reset();
      form.setFocus(useRecovery ? "recovery_code" : "code");
    }
  });

  return (
    <AuthCard
      title="Two-factor verification"
      description={useRecovery ? "Enter one of your saved recovery codes." : "Enter the 6-digit code from your authenticator app."}
      footer={
        <button type="button" onClick={onCancel} className="font-medium text-brand-600 hover:underline">
          Use a different account
        </button>
      }
    >
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {formError && <Alert tone="error">{formError}</Alert>}
          {useRecovery ? (
            <TextField<MfaValues> name="recovery_code" label="Recovery code" autoComplete="one-time-code" />
          ) : (
            <TextField<MfaValues> name="code" label="Authentication code" inputMode="numeric" autoComplete="one-time-code" maxLength={7} placeholder="6-digit code" />
          )}
          <Button type="submit" fullWidth size="lg" loading={isLoading}>
            Verify
          </Button>
          <button
            type="button"
            className="w-full text-center text-sm text-slate-500 hover:text-slate-800"
            onClick={() => {
              setUseRecovery((value) => !value);
              form.clearErrors();
            }}
          >
            {useRecovery ? "Use the authenticator app instead" : "Lost your phone? Use a recovery code"}
          </button>
        </form>
      </FormProvider>
    </AuthCard>
  );
}
