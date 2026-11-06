import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Category, Priority, Ticket, TicketDetail } from "@/modules/support/common/types";
import type { AgentReplyBody, Assignee, QueueFilters, QueueSummary, TicketEvent, Transcript } from "@/modules/support/agent/types";

const ticketTags = (ticketId: string) => [{ type: "SupportTicket" as const, id: ticketId }, "SupportTicketList" as const, "SupportSummary" as const];
type TicketAction = "claim" | "release" | "resolve" | "reopen" | "close";

export const agentTicketsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listQueue: build.query<ListResult<Ticket>, QueueFilters & PageParams>({
      query: (params) => ({ url: "/agent/tickets", params }),
      transformResponse: (response: { tickets: Ticket[]; page_context: PageContext }) => ({ items: response.tickets, pageContext: response.page_context }),
      providesTags: ["SupportTicketList"],
    }),
    getQueueSummary: build.query<QueueSummary[], void>({
      query: () => "/agent/tickets/summary",
      transformResponse: (response: { queues: QueueSummary[] }) => response.queues,
      providesTags: ["SupportSummary"],
    }),
    getAgentTicket: build.query<TicketDetail, string>({
      query: (ticketId) => `/agent/tickets/${ticketId}`,
      providesTags: (_result, _error, ticketId) => [{ type: "SupportTicket", id: ticketId }],
    }),
    getTicketEvents: build.query<TicketEvent[], string>({
      query: (ticketId) => `/agent/tickets/${ticketId}/events`,
      transformResponse: (response: { events: TicketEvent[] }) => response.events,
      providesTags: (_result, _error, ticketId) => [{ type: "SupportTicket", id: ticketId }],
    }),
    getTicketTranscript: build.query<Transcript, string>({
      query: (ticketId) => `/agent/tickets/${ticketId}/transcript`,
      transformResponse: (response: { transcript: Transcript }) => response.transcript,
    }),
    getTicketAssignees: build.query<Assignee[], string>({
      query: (ticketId) => `/agent/tickets/${ticketId}/assignees`,
      transformResponse: (response: { assignees: Assignee[] }) => response.assignees,
    }),
    updateTicket: build.mutation<Ticket, { ticketId: string; priority?: Priority; category?: Category }>({
      query: ({ ticketId, ...body }) => ({ url: `/agent/tickets/${ticketId}`, method: "PATCH", body }),
      transformResponse: (response: { ticket: Ticket }) => response.ticket,
      invalidatesTags: (_result, _error, { ticketId }) => ticketTags(ticketId),
    }),
    agentReply: build.mutation<void, { ticketId: string; body: AgentReplyBody }>({
      query: ({ ticketId, body }) => ({ url: `/agent/tickets/${ticketId}/replies`, method: "POST", body }),
      invalidatesTags: (_result, _error, { ticketId }) => ticketTags(ticketId),
    }),
    ticketAction: build.mutation<Ticket, { ticketId: string; action: TicketAction }>({
      query: ({ ticketId, action }) => ({ url: `/agent/tickets/${ticketId}/${action}`, method: "POST" }),
      transformResponse: (response: { ticket: Ticket }) => response.ticket,
      invalidatesTags: (_result, _error, { ticketId }) => ticketTags(ticketId),
    }),
    assignTicket: build.mutation<Ticket, { ticketId: string; assigneeUserId: string }>({
      query: ({ ticketId, assigneeUserId }) => ({ url: `/agent/tickets/${ticketId}/assign`, method: "POST", body: { assignee_user_id: assigneeUserId } }),
      transformResponse: (response: { ticket: Ticket }) => response.ticket,
      invalidatesTags: (_result, _error, { ticketId }) => ticketTags(ticketId),
    }),
  }),
});

export const {
  useListQueueQuery,
  useGetQueueSummaryQuery,
  useGetAgentTicketQuery,
  useGetTicketEventsQuery,
  useGetTicketTranscriptQuery,
  useGetTicketAssigneesQuery,
  useUpdateTicketMutation,
  useAgentReplyMutation,
  useTicketActionMutation,
  useAssignTicketMutation,
} = agentTicketsApi;
