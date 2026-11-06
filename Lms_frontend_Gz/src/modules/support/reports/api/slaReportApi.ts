import { baseApi } from "@/core/api/baseApi";

export interface SlaReport {
  tickets: number;
  resolved: number;
  first_response_breached: number;
  resolution_breached: number;
  first_response_compliance: number | null;
  resolution_compliance: number | null;
  avg_first_response_minutes: number | null;
  avg_resolution_minutes: number | null;
  csat_responses: number;
  csat_average: number | null;
  reopened: number;
  truncated: boolean;
}

/** Over the agent's own queues; the server defaults to the last 30 days. */
export const slaReportApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getSlaReport: build.query<SlaReport, { start?: string; end?: string }>({
      query: (params) => ({ url: "/agent/reports/sla", params }),
      transformResponse: (response: { report: SlaReport }) => response.report,
      providesTags: ["SupportSummary"],
    }),
  }),
});

export const { useGetSlaReportQuery } = slaReportApi;
