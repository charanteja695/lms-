import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { CallLog } from "@/modules/ai-settings/common/types";

export interface LogFilters {
  organization_id?: string;
  service?: string;
  prompt_key?: string;
  status?: string;
}

/** Every AI call, whatever its outcome. Requests and replies are stored only after personal data is removed. */
export const logsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listAiLogs: build.query<ListResult<CallLog>, LogFilters & PageParams>({
      query: (params) => ({ url: "/logs", params }),
      transformResponse: (r: { logs: CallLog[]; page_context: PageContext }) => ({ items: r.logs, pageContext: r.page_context }),
    }),
  }),
});

export const { useListAiLogsQuery } = logsApi;
