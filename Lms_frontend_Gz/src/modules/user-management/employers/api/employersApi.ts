import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams, SuccessEnvelope } from "@/core/api/types";
import type { StatusChange } from "@/modules/user-management/common/types";
import type { Job } from "@/modules/user-management/downloads/types";
import type { Employer, EmployerBody, EmployerFilters, EmployerListItem } from "@/modules/user-management/employers/types";

export const employersApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listEmployers: build.query<ListResult<EmployerListItem>, EmployerFilters & PageParams>({
      query: (params) => ({ url: "/employers", params }),
      transformResponse: (response: { employers: EmployerListItem[]; page_context: PageContext }) => ({
        items: response.employers,
        pageContext: response.page_context,
      }),
      providesTags: ["EmployerList"],
    }),
    getEmployer: build.query<Employer, string>({
      query: (organizationId) => `/employers/${organizationId}`,
      transformResponse: (response: { employer: Employer }) => response.employer,
      providesTags: (_result, _error, id) => [{ type: "Employer", id }],
    }),
    createEmployer: build.mutation<Employer, EmployerBody>({
      query: (body) => ({ url: "/employers", method: "POST", body }),
      transformResponse: (response: { employer: Employer }) => response.employer,
      invalidatesTags: ["EmployerList", "AdminList"],
    }),
    updateEmployer: build.mutation<Employer, { organizationId: string; body: EmployerBody }>({
      query: ({ organizationId, body }) => ({ url: `/employers/${organizationId}`, method: "PUT", body }),
      transformResponse: (response: { employer: Employer }) => response.employer,
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "Employer", id: organizationId }, "EmployerList", "AdminList"],
    }),
    changeEmployerStatus: build.mutation<Employer, { organizationId: string; status: StatusChange; reason?: string }>({
      query: ({ organizationId, status, reason }) => ({
        url: `/employers/${organizationId}/status`,
        method: "PATCH",
        body: reason ? { status, reason } : { status },
      }),
      transformResponse: (response: { employer: Employer }) => response.employer,
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "Employer", id: organizationId }, "EmployerList"],
    }),
    deleteEmployer: build.mutation<SuccessEnvelope, string>({
      query: (organizationId) => ({ url: `/employers/${organizationId}`, method: "DELETE" }),
      invalidatesTags: (_result, _error, id) => [{ type: "Employer", id }, "EmployerList", "AdminList", "UserList"],
    }),
    revokeEmployer: build.mutation<SuccessEnvelope, string>({
      query: (organizationId) => ({ url: `/employers/${organizationId}/revoke`, method: "POST" }),
    }),
    createEmployerExportJob: build.mutation<Job, EmployerFilters>({
      query: (filters) => ({ url: "/employers/export-jobs", method: "POST", params: filters }),
      transformResponse: (response: { job: Job }) => response.job,
      invalidatesTags: ["Job"],
    }),
  }),
});

export const {
  useListEmployersQuery,
  useGetEmployerQuery,
  useCreateEmployerMutation,
  useUpdateEmployerMutation,
  useChangeEmployerStatusMutation,
  useDeleteEmployerMutation,
  useRevokeEmployerMutation,
  useCreateEmployerExportJobMutation,
} = employersApi;
