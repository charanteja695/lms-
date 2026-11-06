import type { Category, Priority, Queue, TicketStatus } from "@/modules/support/common/types";
import type { BadgeTone } from "@/shared/ui";

export const STATUS_LABELS: Record<TicketStatus, string> = {
  open: "Open", assigned: "Assigned", waiting_on_student: "Waiting on student", resolved: "Resolved", closed: "Closed",
};
export const STATUS_TONES: Record<TicketStatus, BadgeTone> = { open: "blue", assigned: "indigo", waiting_on_student: "amber", resolved: "green", closed: "gray" };

/** What a student sees for "waiting on student": it's their turn. */
export const STUDENT_STATUS_LABELS: Record<TicketStatus, string> = { ...STATUS_LABELS, waiting_on_student: "Waiting for your reply" };

export const CATEGORY_LABELS: Record<Category, string> = {
  learning: "Learning", technical: "Technical", billing: "Billing", integrity: "Exam integrity", access: "Access", other: "Other",
};

export const QUEUE_LABELS: Record<Queue, string> = { batch_staff: "Institution staff", platform_support: "Platform support", exam_team: "Exam team" };

export const PRIORITY_LABELS: Record<Priority, string> = { low: "Low", normal: "Normal", high: "High", urgent: "Urgent" };
export const PRIORITY_TONES: Record<Priority, BadgeTone> = { low: "gray", normal: "blue", high: "amber", urgent: "red" };
