import { baseApi } from "@/core/api/baseApi";
import type { Id, IsoDateTime, ListResult, PageContext, PageParams } from "@/core/api/types";
import type { EscalationStatus } from "@/modules/ai-tutor/common/types";

export interface Escalation {
  escalation_id: Id;
  conversation_id: Id;
  student_user_id: Id;
  organization_id: Id | null;
  course_id: Id | null;
  reason: string;
  category: string;
  status: EscalationStatus;
  ticket_id: Id | null;
  attempts: number;
  last_error: string | null;
  created_at: IsoDateTime;
}

export const escalationsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listEscalations: build.query<ListResult<Escalation>, { status?: EscalationStatus } & PageParams>({
      query: (params) => ({ url: "/escalations", params }),
      transformResponse: (response: { escalations: Escalation[]; page_context: PageContext }) => ({ items: response.escalations, pageContext: response.page_context }),
      providesTags: ["TutorEscalationList"],
    }),
    retryEscalation: build.mutation<Escalation, string>({
      query: (escalationId) => ({ url: `/escalations/${escalationId}/retry`, method: "POST" }),
      transformResponse: (response: { escalation: Escalation }) => response.escalation,
      invalidatesTags: ["TutorEscalationList"],
    }),
  }),
});

export const { useListEscalationsQuery, useRetryEscalationMutation } = escalationsApi;
