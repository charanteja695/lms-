import type { PageContext } from "@/core/api/types";

export interface AssessmentAccessRules {
  chapter_tests: boolean;
  module_tests: boolean;
  final_exam: boolean;
  proctoring: boolean;
}

export interface CourseAccessRules {
  all_approved_courses: boolean;
  course_ids: string[];
}

export type CertificateLevel = "none" | "basic" | "premium" | "pro";

export interface SubscriptionPlan {
  plan_id: string;
  code: string;
  name: string;
  description: string;
  price_paise: number;
  min_price_paise: number | null;
  max_price_paise: number | null;
  billing_duration_days: number;
  billing_label: string;
  max_courses: number | null;
  features: string[];
  course_access_rules: CourseAccessRules;
  assessment_access: AssessmentAccessRules;
  certificate_level: CertificateLevel;
  support_tier: string;
  is_active: boolean;
  is_recommended: boolean;
  display_order: number;
  tier_rank: number;
  created_at: string;
  updated_at: string;
}

export interface PaymentSettings {
  payments_enabled: boolean;
  min_amount_paise: number;
  max_amount_paise: number;
  accepted_methods: Record<string, boolean>;
  tax_rate_percent: number;
  upgrade_pricing_mode: "price_difference" | "full_price";
  upi_vpa: string;
  upi_merchant_name: string;
  gateway_provider: string;
  test_mode: boolean;
  updated_at: string;
}

export interface BrowsePlanPreview {
  plan_id: string;
  code: string;
  name: string;
  price_paise: number;
  billing_duration_days: number;
  billing_label: string;
  max_courses: number | null;
  is_recommended: boolean;
}

export type BrowseAccessStatus =
  | "enrolled"
  | "active_plan"
  | "eligible_under_plan"
  | "available"
  | "payments_disabled";

export interface BrowseCourseItem {
  course_id: string;
  title: string;
  slug: string;
  summary: string;
  thumbnail_media_id: string | null;
  instructor_name: string | null;
  modules_count: number;
  chapters_count: number;
  duration_seconds: number;
  duration_label: string;
  latest_published_version_id: string | null;
  access_status: BrowseAccessStatus;
  active_plan_name: string | null;
  min_price_paise: number | null;
  payments_enabled: boolean;
  plans_preview: BrowsePlanPreview[];
}

export type PaymentActionType = "new" | "upgrade" | "renew";
export type PaymentMethodChoice =
  | "upi"
  | "gpay"
  | "phonepe"
  | "paytm"
  | "card"
  | "netbanking"
  | "wallet"
  | "razorpay"
  | "stripe";

export interface CheckoutSummary {
  plan: SubscriptionPlan;
  course_id: string | null;
  course_title: string | null;
  action_type: PaymentActionType;
  original_amount_paise: number;
  discount_paise: number;
  discount_note: string | null;
  taxable_paise: number;
  tax_paise: number;
  tax_rate_percent: number;
  total_amount_paise: number;
  currency: string;
  accepted_methods: Record<string, boolean>;
  payments_enabled: boolean;
  current_plan_name: string | null;
}

export interface GatewayCheckoutPayload {
  provider: string;
  test_mode: boolean;
  key_id: string | null;
  order_id: string;
  amount: number;
  currency: string;
  seller_name: string;
  upi_qr_payload: string | null;
  expires_at: string | null;
}

export type TxStatus = "pending" | "processing" | "succeeded" | "failed" | "refunded";

export interface StudentPaymentTransaction {
  tx_id: string;
  transaction_ref: string;
  user_id: string;
  plan_id: string;
  plan_code: string;
  plan_name: string;
  course_id: string | null;
  course_title: string | null;
  action_type: PaymentActionType;
  original_amount_paise: number;
  discount_paise: number;
  tax_paise: number;
  total_amount_paise: number;
  currency: string;
  payment_method: string;
  gateway_provider: string;
  gateway_order_id: string;
  gateway_payment_id: string | null;
  upi_qr_payload: string | null;
  status: TxStatus;
  failure_reason: string | null;
  invoice_number: string | null;
  expires_at: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface SubscriptionCourseAccess {
  course_id: string;
  course_title: string;
  granted_at: string;
}

export interface StudentSubscriptionRecord {
  subscription_id: string;
  plan_id: string;
  plan_code: string;
  plan_name: string;
  price_paise: number;
  duration_days: number;
  max_courses: number | null;
  features: string[];
  assessment_access: AssessmentAccessRules;
  certificate_level: CertificateLevel;
  status: "pending" | "active" | "expired" | "superseded" | "cancelled" | "failed";
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
  courses: SubscriptionCourseAccess[];
}

export interface StudentSubscriptionOverview {
  active_subscription: StudentSubscriptionRecord | null;
  history: StudentSubscriptionRecord[];
  available_upgrades: SubscriptionPlan[];
  latest_payment: StudentPaymentTransaction | null;
}

export interface PaymentReceipt {
  transaction_id: string;
  transaction_ref: string;
  invoice_number: string | null;
  plan_name: string;
  course_title: string | null;
  action_type: string;
  original_amount_paise: number;
  discount_paise: number;
  tax_paise: number;
  total_amount_paise: number;
  currency: string;
  payment_method: string;
  gateway_order_id: string;
  gateway_payment_id: string | null;
  status: TxStatus;
  paid_at: string | null;
  created_at: string;
  seller_name: string;
  seller_gstin: string | null;
  seller_state: string;
}

export interface TransactionFilters {
  status?: TxStatus | "";
  from_date?: string;
  to_date?: string;
  search?: string;
  page?: number;
  per_page?: number;
}

export interface TransactionListResult {
  transactions: StudentPaymentTransaction[];
  page_context: PageContext;
}

export type PaymentRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "payment_initiated"
  | "paid"
  | "failed"
  | "cancelled";

export interface StudentAccountContext {
  student_category: "individual" | "institution";
  can_pay_directly: boolean;
  must_request_payment: boolean;
  organization_id: string | null;
}

export interface StudentPaymentRequestRecord {
  request_id: string;
  request_ref: string;
  student_user_id: string;
  student_name: string;
  student_email: string;
  organization_id: string;
  course_id: string;
  course_title: string;
  plan_id: string;
  plan_code: string;
  plan_name: string;
  amount_paise: number;
  status: PaymentRequestStatus;
  student_note: string | null;
  decision_note: string | null;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  paid_by_user_id: string | null;
  paid_at: string | null;
  transaction_id: string | null;
  created_at: string;
}

export interface InstitutionStudentItem {
  student_user_id: string;
  student_name: string;
  student_email: string;
  account_status: string;
  selected_course_id: string | null;
  selected_course_title: string | null;
  active_plan_name: string | null;
  active_subscription_ends_at: string | null;
  payment_status: "active_subscription" | "pending_request" | "approved_request" | "payment_initiated" | "failed" | "unpaid";
  pending_request_id: string | null;
  pending_plan_id: string | null;
  pending_plan_name: string | null;
}

export interface InstitutionAllocationPreview {
  student_user_id: string;
  student_name: string;
  student_email: string;
  course_id: string | null;
  course_title: string | null;
  payment_request_id: string | null;
  original_amount_paise: number;
  discount_paise: number;
  tax_paise: number;
  total_amount_paise: number;
}

export interface InstitutionCheckoutSummary {
  plan: SubscriptionPlan;
  student_count: number;
  currency: string;
  original_total_paise: number;
  discount_total_paise: number;
  tax_rate_percent: number;
  tax_total_paise: number;
  grand_total_paise: number;
  allocations: InstitutionAllocationPreview[];
  accepted_methods: Record<string, boolean>;
  payments_enabled: boolean;
}

export interface StudentPaymentAllocationRecord {
  allocation_id: string;
  transaction_id: string;
  organization_id: string;
  payer_user_id: string;
  student_user_id: string;
  student_name: string;
  student_email: string;
  course_id: string | null;
  course_title: string | null;
  plan_id: string;
  plan_code: string;
  plan_name: string;
  original_amount_paise: number;
  discount_paise: number;
  tax_paise: number;
  allocated_amount_paise: number;
  status: TxStatus;
  activated_at: string | null;
  created_at: string;
}

export interface AdminPaymentReports {
  total_revenue_paise: number;
  independent_revenue_paise: number;
  institution_revenue_paise: number;
  succeeded_count: number;
  pending_count: number;
  failed_count: number;
  pending_requests_count: number;
  active_subscriptions_count: number;
  plan_breakdown: Array<{
    plan_code: string;
    plan_name: string;
    transactions: number;
    revenue_paise: number;
  }>;
  institution_revenue: Array<{
    organization_id: string;
    organization_name: string;
    transactions: number;
    students_covered: number;
    revenue_paise: number;
  }>;
  course_revenue: Array<{
    course_id: string;
    course_title: string;
    transactions: number;
    revenue_paise: number;
  }>;
  plan_revenue: Array<{
    plan_code: string;
    plan_name: string;
    transactions: number;
    revenue_paise: number;
  }>;
}
