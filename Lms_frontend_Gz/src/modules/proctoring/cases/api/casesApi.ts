import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { CaseFilters, MediaAccess, ProctorCase, ProctorCaseDetail, StudentCase } from "@/modules/proctoring/cases/types";

export const casesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listCases: build.query<ListResult<ProctorCase>, CaseFilters & PageParams>({
      query: (params) => ({ url: "/cases", params }),
      transformResponse: (response: { cases: ProctorCase[]; page_context: PageContext }) => ({ items: response.cases, pageContext: response.page_context }),
      providesTags: ["ProctorCaseList"],
    }),
    getCase: build.query<ProctorCaseDetail, string>({
      query: (caseId) => `/cases/${caseId}`,
      transformResponse: (response: { case: ProctorCaseDetail }) => response.case,
      providesTags: (_result, _error, caseId) => [{ type: "ProctorCase", id: caseId }],
    }),
    getSnapshotUrl: build.mutation<{ url: string; expires_in: number }, { caseId: string; snapshotId: string }>({
      query: ({ caseId, snapshotId }) => `/cases/${caseId}/snapshots/${snapshotId}/url`,
    }),
    claimCase: build.mutation<ProctorCase, string>({
      query: (caseId) => ({ url: `/cases/${caseId}/claim`, method: "POST" }),
      transformResponse: (response: { case: ProctorCase }) => response.case,
      invalidatesTags: (_result, _error, caseId) => [{ type: "ProctorCase", id: caseId }, "ProctorCaseList"],
    }),
    decideCase: build.mutation<ProctorCase, { caseId: string; decision: "reviewed_ok" | "invalidated"; note?: string }>({
      query: ({ caseId, decision, note }) => ({ url: `/cases/${caseId}/decide`, method: "POST", body: { decision, note } }),
      transformResponse: (response: { case: ProctorCase }) => response.case,
      invalidatesTags: (_result, _error, { caseId }) => [{ type: "ProctorCase", id: caseId }, "ProctorCaseList"],
    }),
    decideCaseAppeal: build.mutation<ProctorCase, { caseId: string; outcome: "upheld" | "overturned"; note: string }>({
      query: ({ caseId, outcome, note }) => ({ url: `/cases/${caseId}/decide-appeal`, method: "POST", body: { outcome, note } }),
      transformResponse: (response: { case: ProctorCase }) => response.case,
      invalidatesTags: (_result, _error, { caseId }) => [{ type: "ProctorCase", id: caseId }, "ProctorCaseList"],
    }),
    listMediaAccess: build.query<ListResult<MediaAccess>, PageParams>({
      query: (params) => ({ url: "/audit/media-access", params }),
      transformResponse: (response: { accesses: MediaAccess[]; page_context: PageContext }) => ({ items: response.accesses, pageContext: response.page_context }),
      providesTags: ["ProctorMediaAccess"],
    }),

    listMyCases: build.query<StudentCase[], void>({
      query: () => "/my/cases",
      transformResponse: (response: { cases: StudentCase[] }) => response.cases,
      providesTags: ["MyProctorCaseList"],
    }),
    appealCase: build.mutation<StudentCase, { caseId: string; reason: string }>({
      query: ({ caseId, reason }) => ({ url: `/cases/${caseId}/appeal`, method: "POST", body: { reason } }),
      transformResponse: (response: { case: StudentCase }) => response.case,
      invalidatesTags: ["MyProctorCaseList"],
    }),
  }),
});

export const {
  useListCasesQuery,
  useGetCaseQuery,
  useGetSnapshotUrlMutation,
  useClaimCaseMutation,
  useDecideCaseMutation,
  useDecideCaseAppealMutation,
  useListMediaAccessQuery,
  useListMyCasesQuery,
  useAppealCaseMutation,
} = casesApi;
