import { baseApi } from "@/core/api/baseApi";
import type { OptionsHook } from "@/shared/ui";

interface OrgOption {
  organization_id: string;
  name: string;
  industry?: string | null;
}

/** job-portal's own directory of organisations (user-management lets members list only their own). */
export const directoryApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listDirectoryCompanies: build.query<OrgOption[], string>({
      query: (q) => ({ url: "/directory/companies", params: { q: q || undefined } }),
      transformResponse: (response: { organizations: OrgOption[] }) => response.organizations,
    }),
    listDirectoryInstitutions: build.query<OrgOption[], string>({
      query: (q) => ({ url: "/directory/institutions", params: { q: q || undefined } }),
      transformResponse: (response: { organizations: OrgOption[] }) => response.organizations,
    }),
  }),
});

const { useListDirectoryCompaniesQuery, useListDirectoryInstitutionsQuery } = directoryApi;

export const useCompanyOptions: OptionsHook = (search, enabled) => {
  const { data = [], isFetching } = useListDirectoryCompaniesQuery(search, { skip: !enabled });
  return { isFetching, options: data.map((org) => ({ value: org.organization_id, label: org.name, description: org.industry ?? undefined })) };
};

export const useInstitutionDirectoryOptions: OptionsHook = (search, enabled) => {
  const { data = [], isFetching } = useListDirectoryInstitutionsQuery(search, { skip: !enabled });
  return { isFetching, options: data.map((org) => ({ value: org.organization_id, label: org.name })) };
};
