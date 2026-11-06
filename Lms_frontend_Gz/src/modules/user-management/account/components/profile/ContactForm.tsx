import { useMemo, useState } from "react";
import { FormProvider, useForm, useWatch } from "react-hook-form";

import { COMMON_TIMEZONES, LANGUAGES } from "@/core/constants/locale";
import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import { compact, diffForUpdate } from "@/core/lib/query";
import { toContactFormValues, type ContactFormValues } from "@/modules/user-management/account/forms/contactForm";
import { useUpdateMeMutation } from "@/modules/user-management/auth/api/authApi";
import type { User } from "@/modules/user-management/users/types";
import { CheckboxField, FormSection, SelectField, TextField } from "@/shared/form";
import { Button, Card } from "@/shared/ui";

export function ContactForm({ me }: { me: User }) {
  const [updateMe, { isLoading }] = useUpdateMeMutation();
  const notify = useNotify();
  const initial = useMemo(() => toContactFormValues(me), [me]);
  const form = useForm<ContactFormValues>({ defaultValues: initial });
  const includeAddress = useWatch({ control: form.control, name: "include_address" });
  const [saved, setSaved] = useState(false);

  const onSubmit = form.handleSubmit(async (values) => {
    const body: Record<string, unknown> = {};
    const personal = diffForUpdate(initial.personal_info, values.personal_info);
    if (personal) body.personal_info = personal;
    const beforeAddress = initial.include_address ? initial.address : null;
    const afterAddress = values.include_address ? { ...values.address, country: values.address.country.toUpperCase() } : null;
    if (JSON.stringify(beforeAddress) !== JSON.stringify(afterAddress)) body.address = afterAddress ? compact(afterAddress) : null;
    if (!Object.keys(body).length) {
      notify.info("No changes to save");
      return;
    }
    try {
      const updated = await updateMe(body).unwrap();
      form.reset(toContactFormValues(updated));
      setSaved(true);
      notify.success("Profile updated");
    } catch (error) {
      const apiError = toApiError(error);
      const unmatched = applyServerErrors(apiError, form.setError, (field) => /^(personal_info|address)\./.test(field));
      if (unmatched.length || !apiError.details.length) notify.apiError(error, "Profile not updated");
    }
  });

  return (
    <Card title="Contact details" description={saved ? "Saved." : undefined}>
      <FormProvider {...form}>
        <form onSubmit={onSubmit} noValidate>
          <FormSection title="Contact">
            <TextField<ContactFormValues> name="personal_info.phone" label="Phone" type="tel" />
            <TextField<ContactFormValues> name="personal_info.alternate_phone" label="Alternate phone" type="tel" />
            <SelectField<ContactFormValues> name="personal_info.preferred_language" label="Language" options={LANGUAGES} />
            <SelectField<ContactFormValues> name="personal_info.timezone" label="Time zone" options={COMMON_TIMEZONES} />
          </FormSection>
          <FormSection title="Address" actions={<CheckboxField<ContactFormValues> name="include_address" label="Add address" />}>
            {includeAddress ? (
              <>
                <TextField<ContactFormValues> name="address.line1" label="Address line 1" className="sm:col-span-2" required />
                <TextField<ContactFormValues> name="address.line2" label="Address line 2" className="sm:col-span-2" />
                <TextField<ContactFormValues> name="address.city" label="City" required />
                <TextField<ContactFormValues> name="address.state" label="State" required />
                <TextField<ContactFormValues> name="address.postal_code" label="Postal code" required />
                <TextField<ContactFormValues> name="address.country" label="Country code" maxLength={2} required />
              </>
            ) : (
              <p className="text-sm text-slate-500 sm:col-span-2">No address recorded.</p>
            )}
          </FormSection>
          <div className="flex justify-end pt-4">
            <Button type="submit" loading={isLoading} disabled={!form.formState.isDirty}>
              Save changes
            </Button>
          </div>
        </form>
      </FormProvider>
    </Card>
  );
}
