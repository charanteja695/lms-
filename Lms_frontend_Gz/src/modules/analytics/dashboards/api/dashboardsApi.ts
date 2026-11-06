import { baseApi } from "@/core/api/baseApi";
import { DASHBOARD_BY_KEY } from "@/modules/analytics/common/dashboards";
import type { DashboardData, DashboardFilters, DashboardKey } from "@/modules/analytics/common/types";

/** One dashboard's totals for the trailing `days`. The server re-checks who may see what on every call. */
export const dashboardsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getDashboard: build.query<DashboardData, { key: DashboardKey; days: number } & DashboardFilters>({
      query: ({ key, ...params }) => ({ url: `/dashboards/${DASHBOARD_BY_KEY[key].path}`, params }),
      transformResponse: (r: { dashboard: DashboardData }) => r.dashboard,
    }),
  }),
});

export const { useGetDashboardQuery } = dashboardsApi;
