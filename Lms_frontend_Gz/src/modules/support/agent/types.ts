import type { IsoDateTime } from "@/core/api/types";
import type { AttachmentRef, Category, Priority, Queue, TicketStatus } from "@/modules/support/common/types";

export interface QueueFilters {
  status?: TicketStatus;
  queue?: Queue;
  priority?: Priority;
  category?: Category;
  assignee?: string;
  breached?: boolean;
  q?: string;
  sort?: "due" | "activity" | "created";
}

export interface QueueSummary {
  queue: Queue;
  open: number;
  assigned: number;
  waiting_on_student: number;
  unassigned: number;
  breached: number;
  oldest_unanswered_minutes: number | null;
}

export interface TicketEvent {
  event_type: string;
  actor_user_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: IsoDateTime;
}

export interface AgentReplyBody {
  body: string;
  internal?: boolean;
  then?: "waiting_on_student" | "resolved" | null;
  canned_reply_id?: string | null;
  attachments?: AttachmentRef[];
}

export interface Assignee {
  user_id: string;
  name: string;
  role: string;
}

export interface TranscriptMessage {
  message_id: string;
  role: "user" | "assistant";
  kind: string;
  content: string;
  created_at: IsoDateTime;
}

export interface Transcript {
  conversation_id: string;
  mode: string;
  title: string;
  messages: TranscriptMessage[];
}
