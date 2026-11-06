import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { ConversationMode, Rating } from "@/modules/ai-tutor/common/types";
import type { Availability, Conversation, ConversationDetail, SendMessageArgs, Turn } from "@/modules/ai-tutor/chat/types";

export const chatApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getTutorAvailability: build.query<Availability, void>({
      query: () => "/availability",
      transformResponse: (response: { availability: Availability }) => response.availability,
      providesTags: ["TutorAvailability"],
    }),
    listConversations: build.query<ListResult<Conversation>, PageParams>({
      query: (params) => ({ url: "/conversations", params }),
      transformResponse: (response: { conversations: Conversation[]; page_context: PageContext }) => ({ items: response.conversations, pageContext: response.page_context }),
      providesTags: ["TutorConversationList"],
    }),
    getConversation: build.query<ConversationDetail, string>({
      query: (conversationId) => `/conversations/${conversationId}`,
      transformResponse: (response: { conversation: ConversationDetail }) => response.conversation,
      providesTags: (_result, _error, conversationId) => [{ type: "TutorConversation", id: conversationId }],
    }),
    createConversation: build.mutation<Conversation, { mode: ConversationMode; course_id?: string | null }>({
      query: (body) => ({ url: "/conversations", method: "POST", body }),
      transformResponse: (response: { conversation: Conversation }) => response.conversation,
      invalidatesTags: ["TutorConversationList"],
    }),
    deleteConversation: build.mutation<void, string>({
      query: (conversationId) => ({ url: `/conversations/${conversationId}`, method: "DELETE" }),
      invalidatesTags: ["TutorConversationList"],
    }),
    /** The non-streaming send; also the fallback when the streamed request can't be made (see useTutorSend). */
    sendTutorMessage: build.mutation<Turn, SendMessageArgs>({
      query: ({ conversationId, content, context, idempotencyKey }) => ({
        url: `/conversations/${conversationId}/messages`,
        method: "POST",
        body: { content, context, stream: false },
        headers: { "Idempotency-Key": idempotencyKey },
      }),
      transformResponse: (response: { turn: Turn }) => response.turn,
      invalidatesTags: (_result, _error, { conversationId }) => [{ type: "TutorConversation", id: conversationId }, "TutorConversationList"],
    }),
    escalateConversation: build.mutation<Turn, string>({
      query: (conversationId) => ({ url: `/conversations/${conversationId}/escalate`, method: "POST" }),
      transformResponse: (response: { turn: Turn }) => response.turn,
      invalidatesTags: (_result, _error, conversationId) => [{ type: "TutorConversation", id: conversationId }],
    }),
    rateTutorMessage: build.mutation<void, { messageId: string; rating: Rating; comment?: string }>({
      query: ({ messageId, rating, comment }) => ({ url: `/messages/${messageId}/feedback`, method: "POST", body: { rating, comment } }),
    }),
  }),
});

export const {
  useGetTutorAvailabilityQuery,
  useListConversationsQuery,
  useGetConversationQuery,
  useCreateConversationMutation,
  useDeleteConversationMutation,
  useSendTutorMessageMutation,
  useEscalateConversationMutation,
  useRateTutorMessageMutation,
} = chatApi;
