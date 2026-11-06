import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useRevokeCertificateMutation } from "@/modules/certificates/issued/api/certificatesApi";
import { TextareaField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

interface RevokeFormValues {
  reason: string;
}

export function RevokeCertificateDialog({ open, onClose, certificateId }: { open: boolean; onClose: () => void; certificateId: string }) {
  const notify = useNotify();
  const [revoke, { isLoading }] = useRevokeCertificateMutation();
  const form = useForm<RevokeFormValues>({ defaultValues: { reason: "" } });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Revoke this certificate?"
      description="Public verification will report it as revoked (never the reason). This cannot be undone."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="revoke-certificate-form" variant="danger" loading={isLoading}>
            Revoke
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="revoke-certificate-form"
          noValidate
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await revoke({ certificateId, reason: values.reason }).unwrap();
              notify.success("Certificate revoked");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          <TextareaField<RevokeFormValues> name="reason" label="Reason" hint="Kept for staff; never shown publicly." required rows={4} maxLength={1000} />
        </form>
      </FormProvider>
    </Modal>
  );
}
