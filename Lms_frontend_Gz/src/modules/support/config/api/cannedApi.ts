import { baseApi } from "@/core/api/baseApi";
import type { CannedScope } from "@/modules/support/common/types";

export interface CannedReply {
  canned_reply_id: string;
  scope: CannedScope;
  organization_id: string | null;
  title: string;
  body: string;
  active: boolean;
}

export const cannedApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listCannedReplies: build.query<CannedReply[], { include_inactive?: boolean }>({
      query: (params) => ({ url: "/agent/canned-replies", params }),
      transformResponse: (response: { canned_replies: CannedReply[] }) => response.canned_replies,
      providesTags: ["CannedReplyList"],
    }),
    createCannedReply: build.mutation<CannedReply, { scope: CannedScope; title: string; body: string }>({
      query: (body) => ({ url: "/agent/canned-replies", method: "POST", body }),
      transformResponse: (response: { canned_reply: CannedReply }) => response.canned_reply,
      invalidatesTags: ["CannedReplyList"],
    }),
    updateCannedReply: build.mutation<CannedReply, { cannedId: string; title?: string; body?: string; active?: boolean }>({
      query: ({ cannedId, ...body }) => ({ url: `/agent/canned-replies/${cannedId}`, method: "PATCH", body }),
      transformResponse: (response: { canned_reply: CannedReply }) => response.canned_reply,
      invalidatesTags: ["CannedReplyList"],
    }),
    /** Fills `{{student_first_name}}` and `{{ticket_subject}}` for a ticket, server-side. */
    renderCannedReply: build.mutation<string, { cannedId: string; ticketId: string }>({
      query: ({ cannedId, ticketId }) => ({ url: `/agent/canned-replies/${cannedId}/render`, params: { ticket_id: ticketId } }),
      transformResponse: (response: { rendered: { body: string } }) => response.rendered.body,
    }),
  }),
});

export const { useListCannedRepliesQuery, useCreateCannedReplyMutation, useUpdateCannedReplyMutation, useRenderCannedReplyMutation } = cannedApi;
