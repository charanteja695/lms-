import { baseApi } from "@/core/api/baseApi";
import type { Run, RunCreateBody } from "@/modules/code-execution/runs/types";

export const runsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    createRun: build.mutation<Run, RunCreateBody>({
      query: (body) => ({ url: "/runs", method: "POST", body }),
      transformResponse: (response: { run: Run }) => response.run,
    }),
    /** Long-polls: the server holds the request open up to `wait` seconds for the run to finish. */
    getRun: build.query<Run, { runId: string; wait?: number }>({
      query: ({ runId, wait }) => ({ url: `/runs/${runId}`, params: wait ? { wait } : undefined }),
      transformResponse: (response: { run: Run }) => response.run,
    }),
  }),
});

export const { useCreateRunMutation, useLazyGetRunQuery } = runsApi;
