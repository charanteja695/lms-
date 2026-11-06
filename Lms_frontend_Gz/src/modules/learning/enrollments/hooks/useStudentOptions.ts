import { useListUsersQuery } from "@/modules/user-management/users/api/usersApi";
import type { OptionsHook } from "@/shared/ui";

/** Students of one institution, to enrol into a batch. */
export function useStudentOptions(organizationId: string): OptionsHook {
  return (search, enabled) => {
    const { data, isFetching } = useListUsersQuery(
      { search_text: search || undefined, role: "student", organization_id: organizationId, status: "active", per_page: 20, sort_column: "first_name", sort_order: "asc" },
      { skip: !enabled || !organizationId },
    );
    return {
      isFetching,
      options: (data?.items ?? []).map((user) => ({ value: user.user_id, label: user.full_name, description: user.email ?? undefined })),
    };
  };
}
