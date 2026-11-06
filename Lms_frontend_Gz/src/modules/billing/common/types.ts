/** Mirrors billing-service (docs/API.md). Every amount is an integer number of paise. */
export type PriceKind = "course_seat" | "employer_plan";
export type QuoteStatus = "open" | "accepted" | "expired" | "cancelled";
export type InvoiceStatus = "draft" | "issued" | "paid" | "overdue" | "void";
export type PlanStatus = "pending" | "active" | "expired" | "cancelled";

export interface BillingProfile {
  organization_id: string;
  legal_name: string;
  gstin: string | null;
  state: string;
  address: string;
  email: string | null;
  updated_at: string;
}

export type BillingProfileInput = Pick<BillingProfile, "legal_name" | "gstin" | "state" | "address" | "email">;

export interface Price {
  price_id: string;
  kind: PriceKind;
  /** A course id (course_seat) or a tier name (employer_plan). */
  code: string;
  name: string;
  /** Per seat per 365 days for a course; the whole plan for an employer plan. */
  unit_amount: number;
  meta: { job_posts?: number; valid_days?: number };
  active: boolean;
}

export interface QuoteLine {
  course_id: string;
  name: string;
  seats: number;
  term_days: number;
  unit_amount: number;
  amount: number;
}

export interface Quote {
  quote_id: string;
  organization_id: string;
  status: QuoteStatus;
  lines: QuoteLine[];
  subtotal: number;
  discount: number;
  discount_note: string | null;
  gst: number;
  total: number;
  valid_until: string;
  accepted_at: string | null;
  created_at: string;
}

export interface Party {
  legal_name?: string;
  gstin?: string | null;
  state?: string;
  address?: string;
  email?: string | null;
}

export interface Invoice {
  invoice_id: string;
  number: string | null;
  organization_id: string;
  kind: "subscription" | "plan";
  status: InvoiceStatus;
  currency: string;
  subtotal: number;
  discount: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
  amount_paid: number;
  credited: number;
  balance_due: number;
  refund_due: number;
  issue_date: string | null;
  due_date: string | null;
  place_of_supply: string | null;
  customer: Party | null;
  seller: Party;
  note: string | null;
  void_reason: string | null;
  created_at: string;
}

export interface InvoiceLine {
  position: number;
  description: string;
  sac_code: string;
  quantity: number;
  unit_amount: number;
  amount: number;
}

export interface Payment {
  payment_id: string;
  method: string;
  status: "pending" | "succeeded" | "failed";
  amount: number;
  reference: string | null;
  gateway_order_id: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface CreditNote {
  credit_note_id: string;
  number: string;
  reason: string;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
  created_at: string;
}

export interface InvoiceDetail extends Invoice {
  lines: InvoiceLine[];
  payments: Payment[];
  credit_notes: CreditNote[];
}

export interface PlanTier {
  tier: string;
  name: string;
  price: number;
  job_posts: number;
  valid_days: number;
}

export interface OrgPlan {
  plan_id: string;
  tier: string;
  job_posts: number;
  valid_days: number;
  status: PlanStatus;
  starts_at: string | null;
  ends_at: string | null;
}
