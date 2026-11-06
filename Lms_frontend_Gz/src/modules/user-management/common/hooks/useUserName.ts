import { useGetUserQuery } from "@/modules/user-management/users/api/usersApi";

/** See useInstitutionName.ts for why this cross-module resolver hook exists. */
export function useUserName(userId: string) {
  const { data, isFetching } = useGetUserQuery({ resource: "users", userId }, { skip: !userId });
  return { name: data?.personal_info.full_name, isFetching };
}
