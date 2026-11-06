import { FormProvider, useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useForgotPasswordMutation } from "@/modules/user-management/auth/api/authApi";
import { TextField } from "@/shared/form";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Button } from "@/shared/ui";

export function IdentifierStep({ onSent }: { onSent: (identifier: string) => void }) {
  const [forgotPassword, { isLoading }] = useForgotPasswordMutation();
  const notify = useNotify();
  const form = useForm<{ identifier: string }>({ defaultValues: { identifier: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const response = await forgotPassword(values).unwrap();
      notify.info("Check your email", response.message);
      onSent(values.identifier.trim());
    } catch (error) {
      notify.apiError(error, "Could not send the code");
    }
  });

  return (
    <AuthCard
      title="Reset your password"
      description="We'll email a 6-digit code and a reset link to the address on your account."
      footer={<Link to="/login" className="font-medium text-brand-600 hover:underline">Back to sign in</Link>}
    >
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <TextField name="identifier" label="Email or username" autoComplete="username" required />
          <Button type="submit" fullWidth size="lg" loading={isLoading}>
            Send code
          </Button>
        </form>
      </FormProvider>
    </AuthCard>
  );
}
