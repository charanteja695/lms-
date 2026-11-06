import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams, SuccessEnvelope } from "@/core/api/types";
import type { StatusChange } from "@/modules/user-management/common/types";
import type { Job } from "@/modules/user-management/downloads/types";
import type {
  Admin,
  AdminListItem,
  CreatedUser,
  ImportMode,
  ImportResult,
  User,
  UserCreateBody,
  UserFilters,
  UserListItem,
  UserUpdateBody,
} from "@/modules/user-management/users/types";

/** Admins are the same user resource under /admins (super admins only). */
export type UserResource = "users" | "admins";

const listTag = (resource: UserResource): "UserList" | "AdminList" => (resource === "users" ? "UserList" : "AdminList");
const itemTag = (resource: UserResource): "User" | "Admin" => (resource === "users" ? "User" : "Admin");

export const usersApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listUsers: build.query<ListResult<UserListItem>, UserFilters & PageParams>({
      query: (params) => ({ url: "/users", params }),
      transformResponse: (response: { users: UserListItem[]; page_context: PageContext }) => ({
        items: response.users,
        pageContext: response.page_context,
      }),
      providesTags: ["UserList"],
    }),
    listAdmins: build.query<ListResult<AdminListItem>, UserFilters & PageParams>({
      query: (params) => ({ url: "/admins", params }),
      transformResponse: (response: { admins: AdminListItem[]; page_context: PageContext }) => ({
        items: response.admins,
        pageContext: response.page_context,
      }),
      providesTags: ["AdminList"],
    }),
    getUser: build.query<User | Admin, { resource: UserResource; userId: string }>({
      query: ({ resource, userId }) => `/${resource}/${userId}`,
      transformResponse: (response: { user?: User; admin?: Admin }) => (response.user ?? response.admin) as User,
      providesTags: (_result, _error, { resource, userId }) => [{ type: itemTag(resource), id: userId }],
    }),
    createUser: build.mutation<CreatedUser, { resource: UserResource; body: UserCreateBody | Omit<UserCreateBody, "role"> }>({
      query: ({ resource, body }) => ({ url: `/${resource}`, method: "POST", body }),
      transformResponse: (response: { user?: User; admin?: Admin; credentials: CreatedUser["credentials"] }) => ({
        user: (response.user ?? response.admin) as User,
        credentials: response.credentials,
      }),
      invalidatesTags: (_result, _error, { resource }) => [listTag(resource), "InstitutionList", "Institution", "EmployerList", "Employer"],
    }),
    updateUser: build.mutation<User | Admin, { resource: UserResource; userId: string; body: UserUpdateBody }>({
      query: ({ resource, userId, body }) => ({ url: `/${resource}/${userId}`, method: "PUT", body }),
      transformResponse: (response: { user?: User; admin?: Admin }) => (response.user ?? response.admin) as User,
      invalidatesTags: (_result, _error, { resource, userId }) => [
        { type: itemTag(resource), id: userId },
        listTag(resource),
        "Institution",
        "Employer",
      ],
    }),
    changeUserStatus: build.mutation<User | Admin, { resource: UserResource; userId: string; status: StatusChange; reason?: string }>({
      query: ({ resource, userId, status, reason }) => ({
        url: `/${resource}/${userId}/status`,
        method: "PATCH",
        body: reason ? { status, reason } : { status },
      }),
      transformResponse: (response: { user?: User; admin?: Admin }) => (response.user ?? response.admin) as User,
      invalidatesTags: (_result, _error, { resource, userId }) => [{ type: itemTag(resource), id: userId }, listTag(resource)],
    }),
    deleteUser: build.mutation<SuccessEnvelope, { resource: UserResource; userId: string }>({
      query: ({ resource, userId }) => ({ url: `/${resource}/${userId}`, method: "DELETE" }),
      invalidatesTags: (_result, _error, { resource, userId }) => [
        { type: itemTag(resource), id: userId },
        listTag(resource),
        "Institution",
        "InstitutionList",
        "Employer",
        "EmployerList",
      ],
    }),
    revokeUser: build.mutation<SuccessEnvelope, { resource: UserResource; userId: string }>({
      query: ({ resource, userId }) => ({ url: `/${resource}/${userId}/revoke`, method: "POST" }),
    }),
    resetUserMfa: build.mutation<SuccessEnvelope, { resource: UserResource; userId: string }>({
      query: ({ resource, userId }) => ({ url: `/${resource}/${userId}/mfa/reset`, method: "POST" }),
    }),
    setUserPassword: build.mutation<SuccessEnvelope, { resource: UserResource; userId: string; newPassword: string }>({
      query: ({ resource, userId, newPassword }) => ({
        url: `/${resource}/${userId}/password`,
        method: "POST",
        body: { new_password: newPassword },
      }),
      invalidatesTags: (_result, _error, { resource, userId }) => [{ type: itemTag(resource), id: userId }],
    }),
    createUserExportJob: build.mutation<Job, { resource: UserResource; filters: UserFilters }>({
      query: ({ resource, filters }) => ({ url: `/${resource}/export-jobs`, method: "POST", params: filters }),
      transformResponse: (response: { job: Job }) => response.job,
      invalidatesTags: ["Job"],
    }),
    importUsers: build.mutation<SuccessEnvelope & { import_result: ImportResult }, { file: File; dryRun: boolean; mode: ImportMode }>({
      query: ({ file, dryRun, mode }) => {
        const form = new FormData();
        form.append("file", file);
        form.append("dry_run", String(dryRun));
        form.append("mode", mode);
        return { url: "/users/import", method: "POST", body: form };
      },
      invalidatesTags: (result) =>
        result && !result.import_result.dry_run && result.import_result.created > 0 ? ["UserList", "Institution", "InstitutionList"] : [],
    }),
    /** Large files: the worker imports them and produces a downloadable report. */
    createImportJob: build.mutation<Job, { file: File; dryRun: boolean; mode: ImportMode }>({
      query: ({ file, dryRun, mode }) => {
        const form = new FormData();
        form.append("file", file);
        form.append("dry_run", String(dryRun));
        form.append("mode", mode);
        return { url: "/users/import-jobs", method: "POST", body: form };
      },
      transformResponse: (response: { job: Job }) => response.job,
      invalidatesTags: ["Job"],
    }),
  }),
});

export const {
  useListUsersQuery,
  useListAdminsQuery,
  useLazyListUsersQuery,
  useGetUserQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useChangeUserStatusMutation,
  useDeleteUserMutation,
  useRevokeUserMutation,
  useResetUserMfaMutation,
  useSetUserPasswordMutation,
  useCreateUserExportJobMutation,
  useImportUsersMutation,
  useCreateImportJobMutation,
} = usersApi;
