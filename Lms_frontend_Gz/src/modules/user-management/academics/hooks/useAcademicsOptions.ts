import { useListUsersQuery } from "@/modules/user-management/users/api/usersApi";
import type { OptionsHook } from "@/shared/ui";

const LIST = { status: "active", per_page: 20, sort_column: "first_name", sort_order: "asc" } as const;

/** Staff (and the head) of one institution: heads of department and class teachers. */
export function teacherOptionsHook(organizationId: string): OptionsHook {
  return (search, enabled) => {
    const staff = useListUsersQuery({ ...LIST, search_text: search || undefined, role: "staff", organization_id: organizationId }, { skip: !enabled });
    const heads = useListUsersQuery({ ...LIST, search_text: search || undefined, role: "institution_head", organization_id: organizationId }, { skip: !enabled });
    return {
      isFetching: staff.isFetching || heads.isFetching,
      options: [...(heads.data?.items ?? []), ...(staff.data?.items ?? [])].map((u) => ({ value: u.user_id, label: u.full_name, description: u.email ?? undefined })),
    };
  };
}

/** Students of one institution, to place in a section. */
export function studentOptionsHook(organizationId: string): OptionsHook {
  return (search, enabled) => {
    const { data, isFetching } = useListUsersQuery({ ...LIST, search_text: search || undefined, role: "student", organization_id: organizationId }, { skip: !enabled });
    return {
      isFetching,
      options: (data?.items ?? []).map((u) => ({
        value: u.user_id,
        label: u.full_name,
        description: [u.admission_number, u.branch, u.section].filter(Boolean).join(" · ") || (u.email ?? undefined),
      })),
    };
  };
}
