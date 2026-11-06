import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { AuditLog, AuditLogFilters } from "@/modules/user-management/audit-logs/types";

export const auditLogsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listAuditLogs: build.query<ListResult<AuditLog>, AuditLogFilters & PageParams>({
      query: (params) => ({ url: "/audit-logs", params }),
      transformResponse: (response: { audit_logs: AuditLog[]; page_context: PageContext }) => ({
        items: response.audit_logs,
        pageContext: response.page_context,
      }),
      providesTags: ["AuditLog"],
    }),
  }),
});

export const { useListAuditLogsQuery } = auditLogsApi;
