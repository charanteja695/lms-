/** Mirrors ai-tutor-service's enums (see docs/API.md). */
export type ConversationMode = "learning" | "support";

export type MessageKind = "answer" | "faq" | "low_confidence" | "escalation" | "blocked" | "question";

export type FaqScope = "platform" | "organization" | "course";

export type FaqStatus = "draft" | "published" | "archived";

export type EscalationStatus = "pending" | "created" | "failed";

export type Rating = "up" | "down";
