import { baseApi } from "@/core/api/baseApi";

export interface CatalogPermission {
  key: string;
  label: string;
  description: string;
  modules: string[];
  /** platform (admins), institution, employer or member: who may hold it at all. */
  audience: "platform" | "institution" | "employer" | "member";
  default_roles: string[];
}

/** One matrix column. */
export interface MatrixAction {
  key: string;
  label: string;
}

/** One action a page has: its cell key (`students.delete`), what it lets someone do there, who has it by default. */
export interface PageAction {
  action: string;
  key: string;
  meaning: string;
  default_roles: string[];
}

/** One matrix row (module → page). */
export interface MatrixPage {
  key: string;
  label: string;
  group: string;
  description: string;
  holders: string[];
  actions: PageAction[];
}

export interface PermissionCatalog {
  /** Feature keys: an admin's platform areas, and the older company roles' rows. */
  permissions: CatalogPermission[];
  actions: MatrixAction[];
  pages: MatrixPage[];
  /** Roles set on the matrix. */
  matrix_roles: string[];
}

export interface RoleRow {
  role: string;
  permissions: { key: string; allowed: boolean; changed: boolean }[];
}

export interface PersonCell {
  key: string;
  from_role: boolean;
  override: boolean | null;
  allowed: boolean;
}

export interface PersonPermissions {
  editable: boolean;
  permissions: PersonCell[];
}

/** A change per permission: true = allow, false = remove, null = back to the default (role's, or the catalog's). */
export type PermissionChanges = Record<string, boolean | null>;

/** Roles & permissions (super admin). The catalog's labels are readable by anyone signed in. */
export const permissionAdminApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getPermissionCatalog: build.query<PermissionCatalog, void>({
      query: () => "/permissions/catalog",
      transformResponse: ({ permissions, actions, pages, matrix_roles }: PermissionCatalog) => ({ permissions, actions, pages, matrix_roles }),
      providesTags: ["PermissionCatalog"],
      keepUnusedDataFor: 3600,
    }),
    getRolePermissions: build.query<RoleRow[], void>({
      query: () => "/permissions/roles",
      transformResponse: (r: { roles: RoleRow[] }) => r.roles,
      providesTags: ["RolePermissions"],
    }),
    setRolePermissions: build.mutation<RoleRow[], { role: string; changes: PermissionChanges }>({
      query: ({ role, changes }) => ({ url: `/permissions/roles/${role}`, method: "PUT", body: { changes } }),
      transformResponse: (r: { roles: RoleRow[] }) => r.roles,
      invalidatesTags: ["RolePermissions", "PersonPermissions", "Permissions"],
    }),
    getPersonPermissions: build.query<PersonPermissions, string>({
      query: (userId) => `/users/${userId}/permissions`,
      transformResponse: (r: { user_permissions: PersonPermissions }) => r.user_permissions,
      providesTags: (_r, _e, id) => [{ type: "PersonPermissions", id }],
    }),
    setPersonPermissions: build.mutation<PersonPermissions, { userId: string; changes: PermissionChanges; reason?: string }>({
      query: ({ userId, ...body }) => ({ url: `/users/${userId}/permissions`, method: "PUT", body }),
      transformResponse: (r: { user_permissions: PersonPermissions }) => r.user_permissions,
      invalidatesTags: (_r, _e, { userId }) => [{ type: "PersonPermissions", id: userId }, "User"],
    }),
  }),
});

export const { useGetPermissionCatalogQuery, useGetRolePermissionsQuery, useSetRolePermissionsMutation, useGetPersonPermissionsQuery, useSetPersonPermissionsMutation } = permissionAdminApi;
