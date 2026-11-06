import { describe, expect, it } from "vitest";

import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import { toCreateBody, toUpdateBody } from "@/modules/user-management/users/form/userFormBody";
import { emptyUserForm, userToForm } from "@/modules/user-management/users/form/userFormDefaults";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import type { User } from "@/modules/user-management/users/types";

/** Stands in for GET /users/form-options: the server says which sections the form shows. */
function formOptions(overrides: Partial<UserFormOptions> = {}): UserFormOptions {
  return {
    roles: ["staff", "student"],
    role_editable: true,
    organization: { shown: true, type: "institution", required: true, selectable: true, fixed: false },
    scopes: { shown: false, options: [], default: [] },
    manager: { shown: true, role: "staff", defaults_to_you: false },
    sections: { address: true, employment: false, student: true, guardians: true },
    guardians: { max: 4, required_below_age: 18 },
    initial_password: { allowed: true, min_length: 12, generated_without_email: true },
    email_optional: true,
    required_fields: [],
    defaults: { language: "en", timezone: "Asia/Kolkata", country: "IN" },
    ...overrides,
  };
}

function studentForm(): UserFormValues {
  const form = emptyUserForm({ role: "student", organization_id: "358672738414054064", organization_label: "Springfield" });
  form.account.email = "aarav.reddy@example.com";
  form.personal_info.first_name = "Aarav";
  form.personal_info.last_name = "Reddy";
  form.personal_info.date_of_birth = "2012-04-15";
  form.student.admission_number = "ADM/2024/0457";
  form.student.section = "B";
  form.student.graduation_year = "2029";
  form.student.guardians = [{ full_name: "Suresh Reddy", relationship: "father", phone: "+919876543210", email: "", occupation: "", is_primary: false }];
  return form;
}

const existingStaff: User = {
  user_id: "358672738684233908",
  role: "staff",
  status: "active",
  status_reason: null,
  account: { email: "priya@example.com", username: "priya.sharma", email_verified: true, must_change_password: false, last_login_time: null, password_changed_time: null },
  personal_info: {
    first_name: "Priya",
    middle_name: null,
    last_name: "Sharma",
    full_name: "Priya Sharma",
    gender: "female",
    date_of_birth: null,
    phone: "+919812345678",
    alternate_phone: null,
    preferred_language: "en",
    timezone: "Asia/Kolkata",
  },
  address: null,
  employment: { employee_code: "EMP-1024", designation: "Teacher", department: null, employment_type: "full_time", date_of_joining: null },
  student: null,
  institution: { organization_id: "358672738414054064", name: "Springfield", code: "SPH", organization_type: "institution" },
  manager: null,
  created_by: null,
  scopes: [],
  created_time: "2026-09-16T17:57:24Z",
  modified_time: "2026-09-16T17:57:24Z",
  deleted_time: null,
  allowed_actions: ["update", "suspend", "delete"],
};

const staffOptions = formOptions({
  manager: { shown: true, role: "institution_head", defaults_to_you: false },
  sections: { address: true, employment: true, student: false, guardians: false },
});

describe("user form", () => {
  it("builds a compact create body with a primary guardian and academic details", () => {
    expect(toCreateBody(studentForm(), formOptions())).toEqual({
      role: "student",
      organization_id: "358672738414054064",
      account: { email: "aarav.reddy@example.com" },
      personal_info: { first_name: "Aarav", last_name: "Reddy", date_of_birth: "2012-04-15" },
      student: {
        admission_number: "ADM/2024/0457",
        section: "B",
        graduation_year: 2029,
        guardians: [{ full_name: "Suresh Reddy", relationship: "father", phone: "+919876543210", is_primary: true }],
      },
    });
  });

  it("always sends account and personal_info, so a student without email can be created", () => {
    const form = studentForm();
    form.account.email = "";
    expect(toCreateBody(form, formOptions()).account).toEqual({});
    expect(toCreateBody(emptyUserForm({ role: "student" }), formOptions())).toMatchObject({ account: {}, personal_info: {} });
  });

    it("sends only the sections the server showed", () => {
    const form = studentForm();
    form.employment.employee_code = "EMP-NOPE"; // not shown for students
    const body = toCreateBody(form, formOptions()) as unknown as Record<string, unknown>;
    expect(body.employment).toBeUndefined();
  });

  it("sends only changed fields on update", () => {
    const initial = userToForm(existingStaff);
    const edited = structuredClone(initial);
    edited.personal_info.phone = "+919812300000";
    edited.employment.designation = "Senior Teacher";
    expect(toUpdateBody(initial, edited, staffOptions)).toEqual({
      personal_info: { phone: "+919812300000" },
      employment: { designation: "Senior Teacher" },
    });
    expect(toUpdateBody(initial, initial, staffOptions)).toEqual({});
  });

  it("sends the whole address or null when it changes", () => {
    const initial = userToForm(existingStaff);
    const withAddress = structuredClone(initial);
    withAddress.include_address = true;
    withAddress.address = { line1: "12 MG Road", line2: "", city: "Bengaluru", state: "Karnataka", postal_code: "560001", country: "in" };
    expect(toUpdateBody(initial, withAddress, staffOptions)).toEqual({
      address: { line1: "12 MG Road", city: "Bengaluru", state: "Karnataka", postal_code: "560001", country: "IN" },
    });
  });

  it("sends scopes only when the form shows them", () => {
    const initial = userToForm({ ...existingStaff, role: "admin", scopes: ["accounts.manage"] });
    const edited = structuredClone(initial);
    edited.scopes = ["accounts.manage", "careers.manage"];
    const withScopes = formOptions({ scopes: { shown: true, options: ["accounts.manage", "careers.manage"], default: [] } });
    expect(toUpdateBody(initial, edited, withScopes).scopes).toEqual(["accounts.manage", "careers.manage"]);
    expect(toUpdateBody(initial, edited, staffOptions).scopes).toBeUndefined();
  });
});
