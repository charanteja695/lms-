import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Drive, DriveStatus } from "@/modules/job-portal/common/types";

type DriveResponse = { drive: Drive; summary: Record<string, unknown> | null };
const tags = (id: string) => [{ type: "Drive" as const, id }, "Drive" as const];

/** Placement drives: a head proposes one to a verified company, its admin answers, recruiters attach jobs (restricted to that institution). */
export const drivesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listDrives: build.query<ListResult<Drive>, { status?: DriveStatus } & PageParams>({
      query: (params) => ({ url: "/drives", params }),
      transformResponse: (response: { drives: Drive[]; page_context: PageContext }) => ({ items: response.drives, pageContext: response.page_context }),
      providesTags: ["Drive"],
    }),
    getDrive: build.query<DriveResponse, string>({
      query: (id) => `/drives/${id}`,
      providesTags: (_r, _e, id) => [{ type: "Drive", id }],
    }),
    createDrive: build.mutation<
      DriveResponse,
      {
        employer_id: string;
        title: string;
        description?: string;
        drive_date?: string;
        deadline_date?: string;
        institution_id?: string;
        status?: string;
        job_ids?: string[];
      }
    >({
      query: (body) => ({ url: "/drives", method: "POST", body }),
      invalidatesTags: ["Drive", "EmployerJob", "EmployerJobList"],
    }),
    respondToDrive: build.mutation<DriveResponse, { id: string; accept: boolean }>({
      query: ({ id, accept }) => ({ url: `/drives/${id}/respond`, method: "POST", body: { accept } }),
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
    attachJobToDrive: build.mutation<DriveResponse, { id: string; job_id: string }>({
      query: ({ id, job_id }) => ({ url: `/drives/${id}/jobs`, method: "POST", body: { job_id } }),
      invalidatesTags: (_r, _e, { id }) => [...tags(id), "EmployerJob", "EmployerJobList"],
    }),
    finishDrive: build.mutation<DriveResponse, { id: string; action: "complete" | "cancel" }>({
      query: ({ id, action }) => ({ url: `/drives/${id}/${action}`, method: "POST" }),
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
  }),
});

export const { useListDrivesQuery, useGetDriveQuery, useCreateDriveMutation, useRespondToDriveMutation, useAttachJobToDriveMutation, useFinishDriveMutation } = drivesApi;
