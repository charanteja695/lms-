import type { InvoiceStatus, PlanStatus, PriceKind, QuoteStatus } from "@/modules/billing/common/types";

export const QUOTE_STATUS_LABELS: Record<QuoteStatus, string> = { open: "Open", accepted: "Accepted", expired: "Expired", cancelled: "Cancelled" };
export const QUOTE_STATUS_TONES = { open: "blue", accepted: "green", expired: "gray", cancelled: "gray" } as const satisfies Record<QuoteStatus, string>;

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = { draft: "Draft", issued: "Issued", paid: "Paid", overdue: "Overdue", void: "Void" };
export const INVOICE_STATUS_TONES = { draft: "gray", issued: "blue", paid: "green", overdue: "red", void: "gray" } as const satisfies Record<InvoiceStatus, string>;

export const PLAN_STATUS_LABELS: Record<PlanStatus, string> = { pending: "Awaiting payment", active: "Active", expired: "Expired", cancelled: "Cancelled" };
export const PLAN_STATUS_TONES = { pending: "amber", active: "green", expired: "gray", cancelled: "gray" } as const satisfies Record<PlanStatus, string>;

export const PRICE_KIND_LABELS: Record<PriceKind, string> = { course_seat: "Course seat (per seat per year)", employer_plan: "Employer plan" };

export const INVOICE_KIND_LABELS = { subscription: "Course subscription", plan: "Employer plan" } as const;
