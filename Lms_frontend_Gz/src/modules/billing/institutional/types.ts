export interface BulkDiscountTier {
  min_students: number;
  max_students: number | null;
  discount_percent: number;
  fixed_discount_paise: number;
}

export interface InstitutionalCourseItem {
  course_id: string;
  course_title: string;
  course_slug?: string;
}

export interface QuotationCoursePriceItem {
  course_id: string | number;
  course_title: string;
  pricing_method?: string;
  unit_price_paise: number;
  rate_label?: string;
  students?: number;
  duration_days?: number;
  billable_units?: number;
  subtotal_paise?: number;
}

export interface InstitutionalQuotation {
  quotation_number?: string;
  version?: number;
  course_prices: QuotationCoursePriceItem[];
  subtotal_paise: number;
  discount_percent?: number;
  discount_paise: number;
  discount_note?: string;
  taxable_paise?: number;
  tax_rate_percent: number;
  tax_paise: number;
  total_paise: number;
  approved_seats: number;
  approved_duration_days: number;
  package_starts_at?: string | null;
  package_ends_at?: string | null;
  notes?: string;
  quoted_at?: string;
  valid_until?: string;
  expires_at?: string;
}

export interface InstitutionalPaymentInfo {
  order_id?: string;
  payment_id?: string;
  transaction_id?: string;
  amount_paise?: number;
  amount_paid_paise?: number;
  method?: string;
  status?: string;
  paid_at?: string;
  verified: boolean;
}

export interface PurchaseCalculationItem {
  course_id: number;
  course_title: string;
  pricing_method: string;
  rate_paise: number;
  rate_label: string;
  students: number;
  duration_days: number;
  duration_label: string;
  billable_units: number;
  subtotal_paise: number;
}

export interface PurchaseCalculation {
  course_breakdown: PurchaseCalculationItem[];
  total_students: number;
  total_duration_days: number;
  total_duration_months: number;
  starts_at: string;
  ends_at: string;
  subtotal_paise: number;
  bulk_discount_percent: number;
  bulk_discount_paise: number;
  bulk_discount_note: string;
  taxable_paise: number;
  gst_percent: number;
  gst_paise: number;
  grand_total_paise: number;
}

export interface InstitutionalPurchaseRequest {
  public_id: string;
  organization_id: string;
  institution_name: string;
  institution_code?: string;
  contact_person: string;
  contact_email: string;
  contact_phone: string;
  requested_courses: InstitutionalCourseItem[];
  seats_requested: number;
  duration_days_requested: number;
  starts_at_requested?: string | null;
  ends_at_requested?: string | null;
  calculation_breakdown?: PurchaseCalculation | null;
  quotation_versions?: InstitutionalQuotation[];
  message?: string;
  status: "pending" | "quoted" | "accepted" | "paid" | "approved" | "rejected" | "modification_requested";
  quotation?: InstitutionalQuotation | null;
  payment_info?: InstitutionalPaymentInfo | null;
  rejection_reason?: string | null;
  modification_notes?: string | null;
  created_at: string;
  updated_at: string;
  approved_at?: string | null;
  package_starts_at?: string | null;
  package_ends_at?: string | null;
}

export interface InstitutionalPackage {
  request_id: string;
  organization_id: string;
  institution_name: string;
  courses: InstitutionalCourseItem[];
  seats_total: number;
  seats_used: number;
  seats_available: number;
  starts_at?: string;
  ends_at?: string;
  total_paid_paise: number;
  status: string;
}

export interface StudentSeatUsage {
  user_id: string;
  full_name: string;
  email: string;
  course_id: string;
  course_title: string;
  enrolled_at: string;
  status: string;
}

export interface CoursePricingItem {
  course_id: string | number;
  course_title: string;
  course_code?: string;
  category?: string;
  slug?: string;
  individual_price_paise: number;
  pricing_method: "fixed" | "monthly" | "hourly";
  fixed_price_paise: number;
  monthly_price_paise: number;
  monthly_billing_rule: "pro_rata" | "round_up";
  hourly_price_paise: number;
  billable_hours: number;
  bulk_discount_tiers: BulkDiscountTier[];
  gst_percent: number;
  min_students: number;
  max_students: number;
  min_duration_days: number;
  max_duration_days: number;
  effective_from?: string | null;
  expires_at?: string | null;
  is_active: boolean;
  is_published: boolean;
  original_price_paise?: number;
  discount_paise?: number;
  discount_type?: "none" | "percentage" | "fixed";
  discount_percent?: number;
  discount_value?: number;
  valid_days?: number;
  last_updated_at?: string | null;
  last_updated_by?: string | null;
  default_duration_days?: number;
  institutional_price_per_seat_paise?: number;
}

export interface CoursePricingSummary {
  message?: string;
  total_courses: number;
  individual_updates: number;
  institutional_updates: number;
  active_discounts: number;
}

export interface CoursePricingAuditItem {
  id: string;
  public_id: number;
  course_id: number;
  course_title: string;
  course_code?: string;
  previous_individual_price_paise: number;
  new_individual_price_paise: number;
  previous_institutional_price_paise: number;
  new_institutional_price_paise: number;
  pricing_method: string;
  gst_percent: number;
  admin_user_id: number;
  admin_email: string;
  admin_name?: string;
  admin_role?: string;
  reason?: string;
  effective_from?: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export interface CoursePricingHistoryParams {
  course_id?: string | number;
  changed_by?: string;
  price_type?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  per_page?: number;
}

export interface CoursePricingHistoryResponse {
  course_id?: number | null;
  total: number;
  page: number;
  per_page: number;
  audits: CoursePricingAuditItem[];
}
