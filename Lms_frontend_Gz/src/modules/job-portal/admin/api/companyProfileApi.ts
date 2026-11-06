import { baseApi } from "@/core/api/baseApi";
import type { Company } from "@/modules/job-portal/employer/types";

type ProfileBody = Partial<Pick<Company, "about" | "website" | "industry" | "company_size" | "headquarters">>;

/** A company's hiring profile, as the super admin keeps it. `null` while the company has none yet. */
export const companyProfileApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getCompanyHiringProfile: build.query<Company | null, string>({
      queryFn: async (organizationId, _api, _extra, baseQuery) => {
        const result = await baseQuery(`/companies/${organizationId}`);
        if (result.error) return result.error.status === 404 ? { data: null } : { error: result.error };
        return { data: (result.data as { employer: Company }).employer };
      },
      providesTags: (_result, _error, id) => [{ type: "EmployerProfile", id }],
    }),
    keepCompanyProfile: build.mutation<Company, { organizationId: string; body: ProfileBody }>({
      query: ({ organizationId, body }) => ({ url: `/admin/employers/${organizationId}/profile`, method: "PUT", body }),
      transformResponse: (response: { employer: Company }) => response.employer,
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "EmployerProfile", id: organizationId }, "EmployerJobList"],
    }),
  }),
});

export const { useGetCompanyHiringProfileQuery, useKeepCompanyProfileMutation } = companyProfileApi;
