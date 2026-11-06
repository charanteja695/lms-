import { ROLE_LABELS } from "@/modules/user-management/common/labels";
import type { OrganizationType, Role } from "@/modules/user-management/common/types";
import { useListEmployersQuery } from "@/modules/user-management/employers/api/employersApi";
import { useListInstitutionsQuery } from "@/modules/user-management/institutions/api/institutionsApi";
import { useListAdminsQuery, useListUsersQuery } from "@/modules/user-management/users/api/usersApi";
import type { OptionsHook } from "@/shared/ui";

const LIST = { status: "active", per_page: 20, sort_column: "name", sort_order: "asc" } as const;

export const useInstitutionOptions: OptionsHook = (search, enabled) => {
  const { data, isFetching } = useListInstitutionsQuery({ ...LIST, search_text: search || undefined }, { skip: !enabled });
  return {
    isFetching,
    options: (data?.items ?? []).map((item) => ({
      value: item.organization_id,
      label: item.name,
      description: `${item.code} · ${item.city}`,
    })),
  };
};

export const useEmployerOptions: OptionsHook = (search, enabled) => {
  const { data, isFetching } = useListEmployersQuery({ ...LIST, search_text: search || undefined }, { skip: !enabled });
  return {
    isFetching,
    options: (data?.items ?? []).map((item) => ({
      value: item.organization_id,
      label: item.name,
      description: [item.code, item.industry ?? item.city].filter(Boolean).join(" · "),
    })),
  };
};

/** Picker for whichever organisation kind the chosen role belongs to. */
export function organizationOptionsHook(type: OrganizationType | null): OptionsHook {
  return type === "employer" ? useEmployerOptions : useInstitutionOptions;
}

export const useAdminOptions: OptionsHook = (search, enabled) => {
  const { data, isFetching } = useListAdminsQuery(
    { search_text: search || undefined, status: "active", per_page: 20, sort_column: "first_name", sort_order: "asc" },
    { skip: !enabled },
  );
  return {
    isFetching,
    options: (data?.items ?? []).map((item) => ({ value: item.user_id, label: item.full_name, description: item.email ?? undefined })),
  };
};

/** Admins who may own organisations of this kind (the server requires the matching scope). */
export function adminOptionsHook(type: OrganizationType): OptionsHook {
  const scope = type === "employer" ? "careers.manage" : "accounts.manage";
  return (search, enabled) => {
    const { data, isFetching } = useListAdminsQuery(
      { search_text: search || undefined, status: "active", scope, per_page: 20, sort_column: "first_name", sort_order: "asc" },
      { skip: !enabled },
    );
    return {
      isFetching,
      options: (data?.items ?? []).map((item) => ({ value: item.user_id, label: item.full_name, description: item.email ?? undefined })),
    };
  };
}

/** Students the signed-in person may see (their institution's for staff, any for admins) — the server scopes the list. */
export const useStudentOptions: OptionsHook = (search, enabled) => {
  const { data, isFetching } = useListUsersQuery(
    { search_text: search || undefined, role: "student", status: "active", per_page: 20, sort_column: "first_name", sort_order: "asc" },
    { skip: !enabled },
  );
  return {
    isFetching,
    options: (data?.items ?? []).map((item) => ({ value: item.user_id, label: item.full_name, description: item.email ?? undefined })),
  };
};

/** Managers rank above the user and belong to the same organisation; the role comes from form options. */
export function managerOptionsHook(managerRole: Role | null, organizationId: string): OptionsHook {
  return (search, enabled) => {
    const { data, isFetching } = useListUsersQuery(
      {
        search_text: search || undefined,
        role: managerRole && managerRole !== "super_admin" ? managerRole : undefined,
        organization_id: organizationId || undefined,
        status: "active",
        per_page: 20,
        sort_column: "first_name",
        sort_order: "asc",
      },
      { skip: !enabled || !managerRole },
    );
    return {
      isFetching,
      options: (data?.items ?? []).map((item) => ({
        value: item.user_id,
        label: item.full_name,
        description: [ROLE_LABELS[item.role], item.email].filter(Boolean).join(" · "),
      })),
    };
  };
}
