import { baseApi } from "@/core/api/baseApi";

/**
 * ai-tutor-service's `POST /faq/manage/promote`: a tutor answer from a hand-off's transcript becomes an FAQ draft.
 * This module's own call (rule 5 — no import of the ai-tutor module); ai-tutor checks who may promote.
 */
export const promoteApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    promoteTutorAnswer: build.mutation<{ faq: { faq_id: string } }, { messageId: string }>({
      query: ({ messageId }) => ({ url: "/faq/manage/promote", method: "POST", body: { message_id: messageId } }),
      invalidatesTags: ["TutorFaqList"],
    }),
  }),
});

export const { usePromoteTutorAnswerMutation } = promoteApi;
