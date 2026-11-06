import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import { COMMON_TIMEZONES } from "@/core/constants/locale";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { OwningAdminField } from "@/modules/user-management/employers/components/form/OwningAdminField";
import type { EmployerFormValues } from "@/modules/user-management/employers/form/employerForm";
import { FormSection, SelectField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

interface EmployerFormProps {
  mode: "create" | "edit";
  defaultValues: EmployerFormValues;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: EmployerFormValues, form: UseFormReturn<EmployerFormValues>) => Promise<void>;
  onCancel: () => void;
}

export function EmployerForm({ mode, defaultValues, submitting, formError, onSubmit, onCancel }: EmployerFormProps) {
  const { permissions } = usePermissions();
  const form = useForm<EmployerFormValues>({ defaultValues, mode: "onTouched" });

  return (
    <FormProvider {...form}>
      <form noValidate className="space-y-6" onSubmit={form.handleSubmit(async (values) => onSubmit(values, form))}>
        {formError && <Alert tone="error">{formError}</Alert>}
        <Card>
          <FormSection title="Company">
            <TextField<EmployerFormValues> name="name" label="Name" required className="sm:col-span-2" />
            <TextField<EmployerFormValues> name="code" label="Code" required maxLength={20} />
            <TextField<EmployerFormValues> name="industry" label="Industry" placeholder="Information Technology" />
            {permissions.employers.reassign_admin && <OwningAdminField />}
          </FormSection>
          <FormSection title="Contact">
            <TextField<EmployerFormValues> name="contact.email" label="Email" type="email" required />
            <TextField<EmployerFormValues> name="contact.phone" label="Phone" type="tel" required />
            <TextField<EmployerFormValues> name="contact.alternate_phone" label="Alternate phone" type="tel" />
            <TextField<EmployerFormValues> name="contact.website" label="Website" type="url" placeholder="https://" />
          </FormSection>
          <FormSection title="Address">
            <TextField<EmployerFormValues> name="address.line1" label="Address line 1" required className="sm:col-span-2" />
            <TextField<EmployerFormValues> name="address.line2" label="Address line 2" className="sm:col-span-2" />
            <TextField<EmployerFormValues> name="address.city" label="City" required />
            <TextField<EmployerFormValues> name="address.state" label="State" required />
            <TextField<EmployerFormValues> name="address.postal_code" label="Postal code" required />
            <TextField<EmployerFormValues> name="address.country" label="Country code" maxLength={2} required />
          </FormSection>
          <FormSection title="Details" description="Optional.">
            <SelectField<EmployerFormValues> name="timezone" label="Time zone" options={COMMON_TIMEZONES} placeholder="Service default" />
            <TextField<EmployerFormValues> name="established_year" label="Established year" inputMode="numeric" maxLength={4} />
            <TextField<EmployerFormValues> name="registration_number" label="Registration number" placeholder="CIN or GSTIN" />
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "Create employer" : "Save changes"}
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
