import type { Id, IsoDateTime } from "@/core/api/types";
import type { ConversationMode, MessageKind } from "@/modules/ai-tutor/common/types";

export interface Availability {
  enabled: boolean;
  reason: string | null;
  attempt_id: Id | null;
  blocked_until: IsoDateTime | null;
}

export interface Conversation {
  conversation_id: Id;
  mode: ConversationMode;
  course_id: Id | null;
  title: string;
  status: string;
  message_count: number;
  last_message_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export interface LessonCitation {
  type: "lesson";
  number: number;
  item_id: Id;
  item_title: string;
  topic_title: string | null;
  module_title: string | null;
  item_type: string;
  source: "item" | "transcript";
  start_seconds: number | null;
}

export interface FaqCitation {
  type: "faq";
  faq_id: Id;
  question: string;
}

export type Citation = LessonCitation | FaqCitation;

export interface TutorMessage {
  message_id: Id;
  role: "user" | "assistant";
  kind: MessageKind;
  content: string;
  citations: Citation[] | null;
  confidence: number | null;
  retrieval: string | null;
  hint_level: number | null;
  created_at: IsoDateTime;
}

export interface ConversationDetail extends Conversation {
  messages: TutorMessage[];
}

export interface Turn {
  user_message: TutorMessage;
  assistant_message: TutorMessage;
  escalation: { escalation_id: Id; reason: string; category: string; status: string } | null;
}

export interface MessageContext {
  item_id?: string | null;
  code?: string | null;
  language?: string | null;
  hint_request?: boolean;
}

export interface SendMessageArgs {
  conversationId: string;
  content: string;
  context: MessageContext;
  idempotencyKey: string;
}
