import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { useForgotPasswordMutation, useVerifyOtpMutation } from "@/modules/user-management/auth/api/authApi";
import { TextField } from "@/shared/form";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Alert, Button } from "@/shared/ui";

export function OtpStep({ identifier, onVerified, onBack }: { identifier: string; onVerified: (token: string) => void; onBack: () => void }) {
  const [verifyOtp, { isLoading }] = useVerifyOtpMutation();
  const [forgotPassword, resend] = useForgotPasswordMutation();
  const notify = useNotify();
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm<{ otp: string }>({ defaultValues: { otp: "123456" } });

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      const response = await verifyOtp({ identifier, otp: values.otp }).unwrap();
      onVerified(response.password_reset.reset_token);
    } catch (error) {
      setFormError(toApiError(error).message);
      form.reset();
    }
  });

  return (
    <AuthCard
      title="Enter the code"
      description={`We sent a 6-digit code to the email for "${identifier}". It expires in 10 minutes.`}
      footer={
        <div className="flex justify-center gap-4">
          <button type="button" onClick={onBack} className="font-medium text-brand-600 hover:underline">
            Change account
          </button>
          <button
            type="button"
            disabled={resend.isLoading}
            onClick={async () => {
              try {
                await forgotPassword({ identifier }).unwrap();
                notify.info("A new code has been sent");
              } catch (error) {
                notify.apiError(error, "Could not resend the code");
              }
            }}
            className="font-medium text-brand-600 hover:underline disabled:opacity-50"
          >
            Resend code
          </button>
        </div>
      }
    >
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {formError && <Alert tone="error">{formError}</Alert>}
          <TextField name="otp" label="Verification code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="6-digit code" required />
          <Button type="submit" fullWidth size="lg" loading={isLoading}>
            Verify code
          </Button>
        </form>
      </FormProvider>
    </AuthCard>
  );
}
