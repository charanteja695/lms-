import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { AttachmentRef, Category, Ticket, TicketDetail, TicketStatus } from "@/modules/support/common/types";

export interface TicketCreateBody {
  subject: string;
  description: string;
  category: Category;
  course_id?: string | null;
  attachments?: AttachmentRef[];
}

/** The student's side: their own tickets, public messages only. */
export const myTicketsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listMyTickets: build.query<ListResult<Ticket>, { status?: TicketStatus } & PageParams>({
      query: (params) => ({ url: "/tickets", params }),
      transformResponse: (response: { tickets: Ticket[]; page_context: PageContext }) => ({ items: response.tickets, pageContext: response.page_context }),
      providesTags: ["SupportTicketList"],
    }),
    getMyTicket: build.query<TicketDetail, string>({
      query: (ticketId) => `/tickets/${ticketId}`,
      providesTags: (_result, _error, ticketId) => [{ type: "SupportTicket", id: ticketId }],
    }),
    createTicket: build.mutation<Ticket, { body: TicketCreateBody; idempotencyKey: string }>({
      query: ({ body, idempotencyKey }) => ({ url: "/tickets", method: "POST", body, headers: { "Idempotency-Key": idempotencyKey } }),
      transformResponse: (response: { ticket: Ticket }) => response.ticket,
      invalidatesTags: ["SupportTicketList"],
    }),
    replyToMyTicket: build.mutation<void, { ticketId: string; body: string; attachments?: AttachmentRef[] }>({
      query: ({ ticketId, body, attachments = [] }) => ({ url: `/tickets/${ticketId}/replies`, method: "POST", body: { body, attachments } }),
      invalidatesTags: (_result, _error, { ticketId }) => [{ type: "SupportTicket", id: ticketId }, "SupportTicketList"],
    }),
    closeMyTicket: build.mutation<void, string>({
      query: (ticketId) => ({ url: `/tickets/${ticketId}/close`, method: "POST" }),
      invalidatesTags: (_result, _error, ticketId) => [{ type: "SupportTicket", id: ticketId }, "SupportTicketList"],
    }),
    rateMyTicket: build.mutation<void, { ticketId: string; rating: number; comment?: string }>({
      query: ({ ticketId, rating, comment }) => ({ url: `/tickets/${ticketId}/csat`, method: "POST", body: { rating, comment } }),
      invalidatesTags: (_result, _error, { ticketId }) => [{ type: "SupportTicket", id: ticketId }],
    }),
  }),
});

export const {
  useListMyTicketsQuery,
  useGetMyTicketQuery,
  useCreateTicketMutation,
  useReplyToMyTicketMutation,
  useCloseMyTicketMutation,
  useRateMyTicketMutation,
} = myTicketsApi;
