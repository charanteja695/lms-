import type { EscalationStatus, FaqScope, FaqStatus, MessageKind } from "@/modules/ai-tutor/common/types";
import type { BadgeTone } from "@/shared/ui";

export const FAQ_SCOPE_LABELS: Record<FaqScope, string> = { platform: "Platform", organization: "Institution", course: "Course" };

export const FAQ_STATUS_LABELS: Record<FaqStatus, string> = { draft: "Draft", published: "Published", archived: "Archived" };
export const FAQ_STATUS_TONES: Record<FaqStatus, BadgeTone> = { draft: "gray", published: "green", archived: "red" };

export const ESCALATION_STATUS_LABELS: Record<EscalationStatus, string> = { pending: "Pending", created: "Ticket created", failed: "Failed" };
export const ESCALATION_STATUS_TONES: Record<EscalationStatus, BadgeTone> = { pending: "amber", created: "green", failed: "red" };

/** Only the kinds worth flagging on a message; a plain answer or question shows no badge. */
export const MESSAGE_KIND_BADGES: Partial<Record<MessageKind, { label: string; tone: BadgeTone }>> = {
  faq: { label: "From the FAQ", tone: "indigo" },
  low_confidence: { label: "Low confidence", tone: "amber" },
  escalation: { label: "Handed to support", tone: "blue" },
  blocked: { label: "Not answered", tone: "red" },
};
