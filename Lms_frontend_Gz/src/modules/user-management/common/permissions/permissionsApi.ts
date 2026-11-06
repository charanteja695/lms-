import { baseApi } from "@/core/api/baseApi";
import type { Permissions, UserFormOptions } from "@/modules/user-management/common/permissions/types";

/**
 * The backend owns every rule. These two endpoints tell the UI what to show, so no rule is duplicated here.
 * Both are cached: permissions are fetched once per session, form options once per role.
 */
export const permissionsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getMyPermissions: build.query<Permissions, void>({
      query: () => "/users/me/permissions",
      transformResponse: (response: { permissions: Permissions }) => response.permissions,
      providesTags: ["Permissions"],
      keepUnusedDataFor: 3600,
    }),
    getUserFormOptions: build.query<UserFormOptions, { role?: string; userId?: string }>({
      query: ({ role, userId }) => ({ url: "/users/form-options", params: { role, user_id: userId } }),
      transformResponse: (response: { form_options: UserFormOptions }) => response.form_options,
      keepUnusedDataFor: 3600,
    }),
  }),
});

export const { useGetMyPermissionsQuery, useGetUserFormOptionsQuery } = permissionsApi;
