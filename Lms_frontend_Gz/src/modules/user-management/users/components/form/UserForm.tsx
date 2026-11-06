import { useEffect } from "react";
import { FormProvider, useForm, useWatch } from "react-hook-form";

import { COMMON_TIMEZONES, LANGUAGES } from "@/core/constants/locale";
import { toOptions } from "@/core/lib/options";
import { useGetUserFormOptionsQuery } from "@/modules/user-management/common/permissions/permissionsApi";
import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import { EMPLOYMENT_TYPE_LABELS, GENDER_LABELS, ROLE_LABELS } from "@/modules/user-management/common/labels";
import { AddressSection } from "@/modules/user-management/users/components/form/AddressSection";
import { ManagerField } from "@/modules/user-management/users/components/form/ManagerField";
import { OrganizationField } from "@/modules/user-management/users/components/form/OrganizationField";
import { PasswordChoice } from "@/modules/user-management/users/components/form/PasswordChoice";
import { ScopesField } from "@/modules/user-management/users/components/form/ScopesField";
import { StudentSection } from "@/modules/user-management/users/components/form/StudentSection";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { FormSection, SelectField, TextField, FormActions } from "@/shared/form";
import { Alert, Button, Card, PageLoader } from "@/shared/ui";

export interface UserFormProps {
  mode: "create" | "edit";
  defaultValues: UserFormValues;
  /** Set when editing, so the server returns the options for that person. */
  userId?: string;
  submitting: boolean;
  formError?: string | null;
  onSubmit: (values: UserFormValues, form: ReturnType<typeof useForm<UserFormValues>>, options: UserFormOptions) => Promise<void>;
  onCancel: () => void;
}

/**
 * The form is described by the server (`GET /users/form-options`): which roles may be chosen, which sections
 * apply to the chosen role and which fields it requires. Nothing about the rules is decided here.
 */
export function UserForm({ mode, defaultValues, userId, submitting, formError, onSubmit, onCancel }: UserFormProps) {
  const form = useForm<UserFormValues>({ defaultValues, mode: "onTouched" });
  const role = useWatch({ control: form.control, name: "role" });
  const { data: options, isLoading } = useGetUserFormOptionsQuery({ role: role || undefined, userId });
  const onlyRole = options?.roles.length === 1 ? options.roles[0] : undefined;

  // With a single choice (e.g. staff create students, employer admins create recruiters) the role is set for you.
  useEffect(() => {
    if (onlyRole && !role) form.setValue("role", onlyRole);
  }, [form, onlyRole, role]);

  if (isLoading || !options) return <PageLoader />;
  const required = (field: string) => options.required_fields.includes(field);

  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit((values) => onSubmit(values, form, options))} noValidate className="space-y-6">
        {formError && <Alert tone="error">{formError}</Alert>}
        <Card>
          <FormSection title="Role and placement" description="What the person does and where they belong.">
            <SelectField<UserFormValues>
              name="role"
              label="Role"
              options={toOptions(ROLE_LABELS, options.roles)}
              placeholder="Select a role"
              required
              disabled={!options.role_editable}
            />
            {options.organization.shown && <OrganizationField options={options} />}
            {options.manager.shown && <ManagerField options={options} />}
            {options.scopes.shown && <ScopesField options={options.scopes} />}
          </FormSection>

          <FormSection title="Account" description="Used to sign in.">
            <TextField<UserFormValues>
              name="account.email"
              label="Email"
              type="email"
              autoComplete="off"
              required={required("account.email")}
              hint={options.email_optional ? "Optional. Without it, sign-in is by username." : undefined}
            />
            <TextField<UserFormValues>
              name="account.username"
              label="Username"
              hint={mode === "create" ? "Optional. Generated from the name if left empty." : undefined}
              autoComplete="off"
            />
            {options.initial_password.allowed && <PasswordChoice options={options} />}
          </FormSection>

          <PersonalSection options={options} required={required} />

          {options.sections.address && <AddressSection />}
          {options.sections.employment && <EmploymentSection required={required} />}
          {options.sections.student && <StudentSection options={options} />}
        </Card>

        <FormActions>
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" loading={submitting}>
            {mode === "create" ? "Create user" : "Save changes"}
          </Button>
        </FormActions>
      </form>
    </FormProvider>
  );
}

function PersonalSection({ options, required }: { options: UserFormOptions; required: (field: string) => boolean }) {
  return (
    <FormSection title="Personal information" columns={3}>
      <TextField<UserFormValues> name="personal_info.first_name" label="First name" required />
      <TextField<UserFormValues> name="personal_info.middle_name" label="Middle name" />
      <TextField<UserFormValues> name="personal_info.last_name" label="Last name" required />
      <SelectField<UserFormValues> name="personal_info.gender" label="Gender" options={toOptions(GENDER_LABELS)} placeholder="Not specified" />
      <TextField<UserFormValues> name="personal_info.date_of_birth" label="Date of birth" type="date" required={required("personal_info.date_of_birth")} />
      <TextField<UserFormValues> name="personal_info.phone" label="Phone" type="tel" placeholder="+919876543210" required={required("personal_info.phone")} />
      <TextField<UserFormValues> name="personal_info.alternate_phone" label="Alternate phone" type="tel" />
      <SelectField<UserFormValues> name="personal_info.preferred_language" label="Language" options={LANGUAGES} placeholder={`Default (${options.defaults.language})`} />
      <SelectField<UserFormValues> name="personal_info.timezone" label="Time zone" options={COMMON_TIMEZONES} placeholder={`Default (${options.defaults.timezone})`} />
    </FormSection>
  );
}

function EmploymentSection({ required }: { required: (field: string) => boolean }) {
  const needsCode = required("employment.employee_code");
  return (
    <FormSection title="Employment" description={needsCode ? "Employee code must be unique in the organisation." : "Optional."} columns={2}>
      <TextField<UserFormValues> name="employment.employee_code" label="Employee code" required={needsCode} placeholder="EMP-1024" />
      <TextField<UserFormValues> name="employment.designation" label="Designation" placeholder="Mathematics Teacher" />
      <TextField<UserFormValues> name="employment.department" label="Department" />
      <SelectField<UserFormValues> name="employment.employment_type" label="Employment type" options={toOptions(EMPLOYMENT_TYPE_LABELS)} placeholder="Not specified" />
      <TextField<UserFormValues> name="employment.date_of_joining" label="Date of joining" type="date" />
    </FormSection>
  );
}
