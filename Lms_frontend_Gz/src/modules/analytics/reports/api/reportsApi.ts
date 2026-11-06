import { baseApi } from "@/core/api/baseApi";
import type { DashboardFilters, DashboardKey, Report, ReportFormat, ReportFrequency, ReportRun } from "@/modules/analytics/common/types";

const REPORT_TAG = "AnalyticsReport" as const;

/** The signed-in person's own scheduled reports. Creating one re-checks dashboard access with its filters. */
export const reportsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listReports: build.query<Report[], void>({
      query: () => "/reports",
      transformResponse: (r: { reports: Report[] }) => r.reports,
      providesTags: [REPORT_TAG],
    }),
    getReport: build.query<Report, string>({
      query: (id) => `/reports/${id}`,
      transformResponse: (r: { report: Report }) => r.report,
      providesTags: (_r, _e, id) => [{ type: REPORT_TAG, id }],
    }),
    createReport: build.mutation<Report, { name: string; dashboard: DashboardKey; filters: DashboardFilters; frequency: ReportFrequency; format: ReportFormat }>({
      query: (body) => ({ url: "/reports", method: "POST", body }),
      transformResponse: (r: { report: Report }) => r.report,
      invalidatesTags: [REPORT_TAG],
    }),
    deactivateReport: build.mutation<Report, string>({
      query: (id) => ({ url: `/reports/${id}/deactivate`, method: "POST" }),
      invalidatesTags: [REPORT_TAG],
    }),
    runReportNow: build.mutation<ReportRun, string>({
      query: (id) => ({ url: `/reports/${id}/run-now`, method: "POST" }),
      transformResponse: (r: { run: ReportRun }) => r.run,
      invalidatesTags: (_r, _e, id) => [{ type: REPORT_TAG, id: `runs-${id}` }],
    }),
    listReportRuns: build.query<ReportRun[], string>({
      query: (id) => `/reports/${id}/runs`,
      transformResponse: (r: { runs: ReportRun[] }) => r.runs,
      providesTags: (_r, _e, id) => [{ type: REPORT_TAG, id: `runs-${id}` }],
    }),
  }),
});

export const { useListReportsQuery, useGetReportQuery, useCreateReportMutation, useDeactivateReportMutation, useRunReportNowMutation, useListReportRunsQuery } = reportsApi;
