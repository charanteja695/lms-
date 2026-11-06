import { baseApi } from "@/core/api/baseApi";
import type { Id } from "@/core/api/types";

export interface PersonNode {
  user_id: Id;
  full_name: string;
  status: string;
}

export interface InstitutionNode {
  organization_id: Id;
  name: string;
  code: string;
  status: string;
  city: string;
  heads: PersonNode[];
  staff: number;
  students: number;
  departments: number;
}

export interface AdminNode {
  admin: PersonNode | null;
  institutions: InstitutionNode[];
}

export interface Hierarchy {
  super_admins: PersonNode[];
  admins: AdminNode[];
  totals: { admins: number; institutions: number; staff: number; students: number };
}

/** Super admin -> admins -> institutions -> head -> staff and students: the viewer's own part of it. */
export const hierarchyApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getHierarchy: build.query<Hierarchy, void>({
      query: () => "/hierarchy",
      transformResponse: (response: { hierarchy: Hierarchy }) => response.hierarchy,
      providesTags: ["InstitutionList", "AdminList", "UserList"],
    }),
  }),
});

export const { useGetHierarchyQuery } = hierarchyApi;
