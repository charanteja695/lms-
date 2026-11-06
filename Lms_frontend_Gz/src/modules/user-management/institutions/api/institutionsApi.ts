import type { RootState } from "@/app/store";
import { baseApi, refreshSession } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams, SuccessEnvelope } from "@/core/api/types";
import type { StatusChange } from "@/modules/user-management/common/types";
import type { Job } from "@/modules/user-management/downloads/types";
import type { Institution, InstitutionBody, InstitutionFilters, InstitutionListItem } from "@/modules/user-management/institutions/types";

export const institutionsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listInstitutions: build.query<ListResult<InstitutionListItem>, InstitutionFilters & PageParams>({
      query: (params) => ({ url: "/institutions", params }),
      transformResponse: (response: { institutions: InstitutionListItem[]; page_context: PageContext }) => ({
        items: response.institutions,
        pageContext: response.page_context,
      }),
      providesTags: ["InstitutionList"],
    }),
    getInstitution: build.query<Institution, string>({
      query: (organizationId) => `/institutions/${organizationId}`,
      transformResponse: (response: { institution: Institution }) => response.institution,
      providesTags: (_result, _error, id) => [{ type: "Institution", id }],
    }),
    createInstitution: build.mutation<Institution, InstitutionBody>({
      query: (body) => ({ url: "/institutions", method: "POST", body }),
      transformResponse: (response: { institution: Institution }) => response.institution,
      invalidatesTags: ["InstitutionList", "AdminList"],
      // An admin's token lists the institutions they look after (other services scope their lists by it):
      // refresh it now so the new institution shows up everywhere at once.
      async onQueryStarted(_body, { dispatch, getState, queryFulfilled }) {
        const { data } = await queryFulfilled.catch(() => ({ data: null }));
        if (data && (getState() as RootState).auth.user?.role === "admin") {
          await refreshSession({ dispatch, getState, signal: new AbortController().signal, abort: () => {}, extra: undefined, endpoint: "createInstitution", type: "mutation" });
        }
      },
    }),
    updateInstitution: build.mutation<Institution, { organizationId: string; body: InstitutionBody }>({
      query: ({ organizationId, body }) => ({ url: `/institutions/${organizationId}`, method: "PUT", body }),
      transformResponse: (response: { institution: Institution }) => response.institution,
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "Institution", id: organizationId }, "InstitutionList", "AdminList"],
    }),
    changeInstitutionStatus: build.mutation<Institution, { organizationId: string; status: StatusChange; reason?: string }>({
      query: ({ organizationId, status, reason }) => ({
        url: `/institutions/${organizationId}/status`,
        method: "PATCH",
        body: reason ? { status, reason } : { status },
      }),
      transformResponse: (response: { institution: Institution }) => response.institution,
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "Institution", id: organizationId }, "InstitutionList"],
    }),
    deleteInstitution: build.mutation<SuccessEnvelope, string>({
      query: (organizationId) => ({ url: `/institutions/${organizationId}`, method: "DELETE" }),
      invalidatesTags: (_result, _error, id) => [{ type: "Institution", id }, "InstitutionList", "AdminList", "UserList"],
    }),
    revokeInstitution: build.mutation<SuccessEnvelope, string>({
      query: (organizationId) => ({ url: `/institutions/${organizationId}/revoke`, method: "POST" }),
    }),
    createInstitutionExportJob: build.mutation<Job, InstitutionFilters>({
      query: (filters) => ({ url: "/institutions/export-jobs", method: "POST", params: filters }),
      transformResponse: (response: { job: Job }) => response.job,
      invalidatesTags: ["Job"],
    }),
  }),
});

export const {
  useListInstitutionsQuery,
  useGetInstitutionQuery,
  useCreateInstitutionMutation,
  useUpdateInstitutionMutation,
  useChangeInstitutionStatusMutation,
  useDeleteInstitutionMutation,
  useRevokeInstitutionMutation,
  useCreateInstitutionExportJobMutation,
} = institutionsApi;
