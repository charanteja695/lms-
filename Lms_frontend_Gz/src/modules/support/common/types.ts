import type { Id, IsoDateTime } from "@/core/api/types";

/** Mirrors support-service's enums (see docs/API.md). */
export type TicketStatus = "open" | "assigned" | "waiting_on_student" | "resolved" | "closed";
export type Category = "learning" | "technical" | "billing" | "integrity" | "access" | "other";
export type Queue = "batch_staff" | "platform_support" | "exam_team";
export type Priority = "low" | "normal" | "high" | "urgent";
export type CannedScope = "platform" | "organization";

export interface Ticket {
  ticket_id: Id;
  subject: string;
  category: Category;
  queue: Queue;
  priority: Priority;
  status: TicketStatus;
  source: "portal" | "ai-tutor";
  source_ref?: string | null;
  course_id: Id | null;
  requester_user_id: Id;
  organization_id: Id | null;
  assignee_user_id: Id | null;
  first_response_due_at: IsoDateTime | null;
  resolution_due_at: IsoDateTime | null;
  first_response_breached: boolean;
  resolution_breached: boolean;
  first_response_at: IsoDateTime | null;
  resolved_at: IsoDateTime | null;
  closed_at: IsoDateTime | null;
  reopened_count: number;
  csat_requested_at: IsoDateTime | null;
  csat_rating: number | null;
  created_at: IsoDateTime;
  last_activity_at: IsoDateTime | null;
}

/** A file on a message; its bytes are fetched through a short-lived link (see attachmentsApi). */
export interface Attachment {
  filename: string;
  content_type: string;
  size_bytes: number;
}

/** What a new ticket or a reply sends for a file uploaded beforehand. */
export interface AttachmentRef {
  key: string;
  filename: string;
}

export interface TicketMessage {
  message_id: Id;
  seq: number;
  author_user_id: Id | null;
  author_role: string;
  kind: "public" | "internal";
  body: string;
  attachments: Attachment[];
  created_at: IsoDateTime;
}

export interface TicketDetail {
  ticket: Ticket;
  messages: TicketMessage[];
  requester_name: string | null;
  assignee_name: string | null;
}
