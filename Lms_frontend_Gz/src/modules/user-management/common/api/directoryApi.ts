import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext } from "@/core/api/types";
import type { OrganizationType } from "@/modules/user-management/common/types";

export interface DirectoryEntry {
  organization_id: string;
  organization_type: OrganizationType;
  name: string;
  code: string;
  city: string;
  status: string;
}

/**
 * Names-only organisation lookup for platform staff (admins of any scope, super admins). `/institutions` and
 * `/employers` list only what an admin owns; this lets an analytics or careers admin pick or name any of them.
 */
export const directoryApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    searchDirectory: build.query<ListResult<DirectoryEntry>, { type: OrganizationType; search_text?: string; per_page?: number }>({
      query: (params) => ({ url: "/directory/organizations", params: { sort_order: "asc", ...params } }),
      transformResponse: (r: { organizations: DirectoryEntry[]; page_context: PageContext }) => ({ items: r.organizations, pageContext: r.page_context }),
    }),
    getDirectoryEntry: build.query<DirectoryEntry, string>({
      query: (id) => `/directory/organizations/${id}`,
      transformResponse: (r: { organization: DirectoryEntry }) => r.organization,
      keepUnusedDataFor: 3600,
    }),
  }),
});

export const { useSearchDirectoryQuery, useGetDirectoryEntryQuery } = directoryApi;
