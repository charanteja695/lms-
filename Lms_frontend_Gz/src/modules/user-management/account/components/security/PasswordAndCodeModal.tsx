import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import { useDisableMfaMutation, useRegenerateRecoveryCodesMutation } from "@/modules/user-management/auth/api/authApi";
import { PasswordField, TextField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";


interface ConfirmValues {
  password: string;
  code: string;
}

export function PasswordAndCodeModal({ open, purpose, onClose, onCodes, onDisabled }: {
  open: boolean;
  purpose: "disable" | "codes";
  onClose: () => void;
  onCodes: (codes: string[]) => void;
  onDisabled: () => void;
}) {
  const [disable, disabling] = useDisableMfaMutation();
  const [regenerate, regenerating] = useRegenerateRecoveryCodesMutation();
  const notify = useNotify();
  const form = useForm<ConfirmValues>({ defaultValues: { password: "", code: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      if (purpose === "disable") {
        await disable(values).unwrap();
        notify.success("Two-factor authentication turned off");
        onDisabled();
      } else {
        onCodes(await regenerate(values).unwrap());
      }
      form.reset();
    } catch (error) {
      const apiError = toApiError(error);
      const unmatched = applyServerErrors(apiError, form.setError, (field) => field in values);
      if (unmatched.length || !apiError.details.length) notify.apiError(error);
    }
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={purpose === "disable" ? "Turn off two-factor authentication" : "Create new recovery codes"}
      description={purpose === "codes" ? "Your previous recovery codes will stop working." : "Your account will be protected by your password only."}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant={purpose === "disable" ? "danger" : "primary"} loading={disabling.isLoading || regenerating.isLoading} onClick={() => void onSubmit()}>
            {purpose === "disable" ? "Turn off" : "Create codes"}
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <PasswordField<ConfirmValues> name="password" label="Current password" required />
          <TextField<ConfirmValues> name="code" label="Authentication code" inputMode="numeric" maxLength={6} autoComplete="one-time-code" required />
        </form>
      </FormProvider>
    </Modal>
  );
}
