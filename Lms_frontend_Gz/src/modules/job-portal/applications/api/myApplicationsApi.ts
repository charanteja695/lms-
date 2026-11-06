import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { MyApplication } from "@/modules/job-portal/applications/types";
import type { ApplicationStatus } from "@/modules/job-portal/common/types";

const tags = (id: string) => [{ type: "MyApplication" as const, id }, "MyApplication" as const, "JobBoard" as const];

export const myApplicationsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listMyApplications: build.query<ListResult<MyApplication>, { status?: ApplicationStatus; active?: boolean } & PageParams>({
      query: (params) => ({ url: "/applications", params }),
      transformResponse: (response: { applications: MyApplication[]; page_context: PageContext }) => ({ items: response.applications, pageContext: response.page_context }),
      providesTags: ["MyApplication"],
    }),
    getMyApplication: build.query<MyApplication, string>({
      query: (id) => `/applications/${id}`,
      transformResponse: (response: { application: MyApplication }) => response.application,
      providesTags: (_r, _e, id) => [{ type: "MyApplication", id }],
    }),
    withdrawApplication: build.mutation<void, { id: string; note?: string }>({
      query: ({ id, note }) => ({ url: `/applications/${id}/withdraw`, method: "POST", body: { note } }),
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
    respondToOffer: build.mutation<void, { id: string; accept: boolean; note?: string }>({
      query: ({ id, accept, note }) => ({ url: `/applications/${id}/offer/respond`, method: "POST", body: { accept, note } }),
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
  }),
});

export const { useListMyApplicationsQuery, useGetMyApplicationQuery, useWithdrawApplicationMutation, useRespondToOfferMutation } = myApplicationsApi;
