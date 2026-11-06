import { compact, diffForUpdate } from "@/core/lib/query";
import type { UserFormOptions } from "@/modules/user-management/common/permissions/types";
import type { UserFormValues } from "@/modules/user-management/users/form/userFormValues";
import type { UserCreateBody, UserUpdateBody } from "@/modules/user-management/users/types";

const NUMERIC_STUDENT_FIELDS = ["year_of_study", "graduation_year"] as const;

/**
 * Request shape shared by create and update. Only the sections the server showed are sent, so the rules
 * about which sections apply stay in the backend (`form_options.sections`).
 */
function toRequestShape(values: UserFormValues, options: UserFormOptions) {
  const student = {
    ...values.student,
    ...Object.fromEntries(
      NUMERIC_STUDENT_FIELDS.map((field) => [field, values.student[field] === "" ? "" : Number(values.student[field])]),
    ),
    guardians: values.student.guardians.map((guardian, _index, all) => ({
      ...guardian,
      is_primary: all.length === 1 ? true : guardian.is_primary,
    })),
  };
  return {
    role: values.role,
    organization_id: options.organization.shown ? values.organization_id : "",
    manager_user_id: options.manager.shown ? values.manager_user_id : "",
    scopes: options.scopes.shown ? values.scopes : undefined,
    account: { email: values.account.email, username: values.account.username },
    personal_info: values.personal_info,
    address: values.include_address ? { ...values.address, country: values.address.country.toUpperCase() } : null,
    employment: options.sections.employment ? values.employment : null,
    student: options.sections.student ? student : null,
  };
}

export function toCreateBody(values: UserFormValues, options: UserFormOptions): UserCreateBody {
  const shape = toRequestShape(values, options);
  const body = compact({
    ...shape,
    account: {
      ...shape.account,
      password: values.account.set_password ? values.account.password : undefined,
      generate_password: values.account.generate_password ? true : undefined,
    },
    address: shape.address ?? undefined,
    employment: shape.employment ?? undefined,
    student: shape.student ?? undefined,
  });
  // Always send these two, even empty: a student without email or username is valid (the server makes the username),
  // and an empty name must come back as errors on the name fields, not as one "personal_info is required".
  return { ...body, account: body.account ?? {}, personal_info: body.personal_info ?? {} } as UserCreateBody;
}

/** Only changed fields; whole address and guardian list when they change (the API replaces them). */
export function toUpdateBody(initial: UserFormValues, values: UserFormValues, options: UserFormOptions): UserUpdateBody {
  const before = toRequestShape(initial, options);
  const after = toRequestShape(values, options);
  const body: Record<string, unknown> = {};

  const simple = diffForUpdate(
    {
      role: before.role,
      organization_id: before.organization_id,
      manager_user_id: before.manager_user_id,
      account: before.account,
      personal_info: before.personal_info,
      employment: before.employment,
    },
    {
      role: after.role,
      organization_id: after.organization_id,
      manager_user_id: after.manager_user_id,
      account: after.account,
      personal_info: after.personal_info,
      employment: after.employment,
    },
  ) as Record<string, unknown> | undefined;
  Object.assign(body, simple ?? {});

  if (options.scopes.shown && JSON.stringify([...initial.scopes].sort()) !== JSON.stringify([...values.scopes].sort())) {
    body.scopes = values.scopes;
  }
  if (JSON.stringify(before.address) !== JSON.stringify(after.address)) body.address = after.address ? compact(after.address) : null;
  if (after.student) {
    const studentChanges = (diffForUpdate({ ...before.student, guardians: undefined }, { ...after.student, guardians: undefined }) ?? {}) as Record<string, unknown>;
    if (JSON.stringify(compact(before.student?.guardians ?? [])) !== JSON.stringify(compact(after.student.guardians))) {
      studentChanges.guardians = compact(after.student.guardians);
    }
    if (Object.keys(studentChanges).length) body.student = studentChanges;
  }
  return body;
}
