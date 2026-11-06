import { FormProvider, useForm, type UseFormReturn } from "react-hook-form";

import { COMMON_TIMEZONES } from "@/core/constants/locale";
import { toOptions } from "@/core/lib/options";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { INSTITUTION_TYPE_LABELS } from "@/modules/user-management/common/labels";
import { AdminField } from "@/modules/user-management/institutions/components/form/AdminField";
import type { InstitutionFormValues } from "@/modules/user-management/institutions/form/institutionFormValues";
import { FormSection, SelectField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card } from "@/shared/ui";

export function InstitutionForm({ mode, defaultValues, submitting, formError, onSubmit, onCancel }: {
  mode: "create" | "edit";
  defaultValues: InstitutionFormValues;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: InstitutionFormValues, form: UseFormReturn<InstitutionFormValues>) => Promise<void>;
  onCancel: () => void;
}) {
  const { role } = useAuth();
  const form = useForm<InstitutionFormValues>({ defaultValues, mode: "onTouched" });

  return (
    <FormProvider {...form}>
      <form
        noValidate
        className="space-y-6"
        onSubmit={form.handleSubmit(async (values) => {
          await onSubmit(values, form);
        })}
      >
        {formError && <Alert tone="error">{formError}</Alert>}
        <Card>
          <FormSection title="Institution">
            <TextField<InstitutionFormValues> name="name" label="Name" required className="sm:col-span-2" />
            <TextField<InstitutionFormValues> name="code" label="Code" required maxLength={20} />
            <SelectField<InstitutionFormValues> name="type" label="Type" options={toOptions(INSTITUTION_TYPE_LABELS)} placeholder="Select a type" required />
            {role === "super_admin" && <AdminField />}
          </FormSection>
          <FormSection title="Contact">
            <TextField<InstitutionFormValues> name="contact.email" label="Email" type="email" required />
            <TextField<InstitutionFormValues> name="contact.phone" label="Phone" type="tel" required />
            <TextField<InstitutionFormValues> name="contact.alternate_phone" label="Alternate phone" type="tel" />
            <TextField<InstitutionFormValues> name="contact.website" label="Website" type="url" placeholder="https://" />
          </FormSection>
          <FormSection title="Address">
            <TextField<InstitutionFormValues> name="address.line1" label="Address line 1" required className="sm:col-span-2" />
            <TextField<InstitutionFormValues> name="address.line2" label="Address line 2" className="sm:col-span-2" />
            <TextField<InstitutionFormValues> name="address.city" label="City" required />
            <TextField<InstitutionFormValues> name="address.state" label="State" required />
            <TextField<InstitutionFormValues> name="address.postal_code" label="Postal code" required />
            <TextField<InstitutionFormValues> name="address.country" label="Country code" maxLength={2} required />
          </FormSection>
          <FormSection title="Details" description="Optional.">
            <SelectField<InstitutionFormValues> name="timezone" label="Time zone" options={COMMON_TIMEZONES} placeholder="Default (Asia/Kolkata)" />
            <TextField<InstitutionFormValues> name="established_year" label="Established year" inputMode="numeric" maxLength={4} />
            <TextField<InstitutionFormValues> name="registration_number" label="Registration number" />
            <TextField<InstitutionFormValues> name="affiliation" label="Affiliation" placeholder="e.g. CBSE" />
          </FormSection>
        </Card>
        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "Create institution" : "Save changes"}
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}
