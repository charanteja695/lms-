import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import { FormGrid } from "@/modules/user-management/manage/common/components/FormGrid";
import { GuardianFields } from "@/modules/user-management/manage/people/components/GuardianFields";
import type { PersonKind } from "@/modules/user-management/manage/people/config";
import { OrganizationField } from "@/modules/user-management/users/components/form/OrganizationField";
import { PasswordChoice } from "@/modules/user-management/users/components/form/PasswordChoice";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import { TextField } from "@/shared/form";

/**
 * Only the fields this kind of person needs. Which sections apply and which fields are required comes from the
 * server (`GET /users/form-options`); everything else it knows about a person can wait.
 */
export function PersonFields({ kind, options, editing }: { kind: PersonKind; options: UserFormOptions; editing?: boolean }) {
  const required = (field: string) => options.required_fields.includes(field);

  return (
    <div className="space-y-6">
      {options.organization.shown && (
        <FormGrid>
          <div className="sm:col-span-2">
            <OrganizationField options={options} />
          </div>
        </FormGrid>
      )}

      <FormGrid title="Person">
        <TextField<UserFormValues> name="personal_info.first_name" label="First name" required />
        <TextField<UserFormValues> name="personal_info.last_name" label="Last name" required />
        <TextField<UserFormValues>
          name="account.email"
          label="Email"
          type="email"
          autoComplete="off"
          required={required("account.email")}
          hint={options.email_optional ? "Optional. Without it they sign in with a username." : undefined}
        />
        <TextField<UserFormValues> name="personal_info.phone" label="Phone" type="tel" placeholder="+919876543210" required={required("personal_info.phone")} />
        {options.sections.student && (
          <TextField<UserFormValues> name="personal_info.date_of_birth" label="Date of birth" type="date" required={required("personal_info.date_of_birth")} />
        )}
      </FormGrid>

      {!editing && options.initial_password.allowed && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <PasswordChoice options={options} />
        </div>
      )}

      {options.sections.employment && kind !== "admin" && (
        <FormGrid title="Work">
          <TextField<UserFormValues> name="employment.employee_code" label="Employee code" placeholder="EMP-1024" required={required("employment.employee_code")} />
          <TextField<UserFormValues> name="employment.department" label="Department" placeholder={kind === "staff" ? "e.g. Mathematics" : undefined} />
        </FormGrid>
      )}

      {options.sections.student && (
        <FormGrid title="Studies">
          <TextField<UserFormValues> name="student.admission_number" label="Admission number" placeholder="ADM/2024/0457" required />
          <TextField<UserFormValues> name="student.program" label="Programme" placeholder="e.g. B.Tech" />
          <TextField<UserFormValues> name="student.branch" label="Branch" placeholder="e.g. Computer Science" />
          <div className="grid grid-cols-2 gap-4">
            <TextField<UserFormValues> name="student.year_of_study" label="Year" type="number" placeholder="1" />
            <TextField<UserFormValues> name="student.section" label="Section" placeholder="A" />
          </div>
        </FormGrid>
      )}

      {options.sections.guardians && <GuardianFields requiredBelowAge={options.guardians.required_below_age} max={options.guardians.max} />}
    </div>
  );
}
