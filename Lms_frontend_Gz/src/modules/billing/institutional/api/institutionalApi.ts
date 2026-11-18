import { baseApi } from "@/core/api/baseApi";
import type {
  CoursePricingAuditItem,
  CoursePricingHistoryParams,
  CoursePricingHistoryResponse,
  CoursePricingItem,
  CoursePricingSummary,
  InstitutionalPackage,
  InstitutionalPurchaseRequest,
  PurchaseCalculation,
  StudentSeatUsage,
} from "../types";

export const institutionalApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // Institution Head Endpoints
    getInstitutionRequests: build.query<InstitutionalPurchaseRequest[], void>({
      query: () => "/institution/course-requests",
      transformResponse: (r: { items?: InstitutionalPurchaseRequest[]; requests?: InstitutionalPurchaseRequest[] }) =>
        r.items || r.requests || [],
      providesTags: ["CourseRequestList"],
    }),

    getInstitutionRequestDetail: build.query<InstitutionalPurchaseRequest, string>({
      query: (id) => `/institution/course-requests/${id}`,
      transformResponse: (r: { request: InstitutionalPurchaseRequest }) => r.request,
      providesTags: ["CourseRequest"],
    }),

    getInstitutionCoursePricing: build.query<CoursePricingItem[], void>({
      query: () => "/institution/course-pricing",
      transformResponse: (r: { items?: CoursePricingItem[]; course_pricing?: CoursePricingItem[] }) =>
        r.items || r.course_pricing || [],
      providesTags: ["Store"],
    }),

    calculateInstitutionalPurchase: build.mutation<
      PurchaseCalculation,
      {
        course_ids: number[];
        students: number;
        starts_at: string;
        ends_at: string;
      }
    >({
      query: (body) => ({
        url: "/institution/course-pricing/calculate",
        method: "POST",
        body,
      }),
      transformResponse: (r: { calculation: PurchaseCalculation }) => r.calculation,
    }),

    submitInstitutionRequest: build.mutation<
      InstitutionalPurchaseRequest,
      {
        contact_person: string;
        contact_email: string;
        contact_phone: string;
        requested_courses: Array<{ course_id: number | string; course_title: string; course_slug?: string }>;
        seats_requested: number;
        duration_days_requested: number;
        starts_at?: string;
        ends_at?: string;
        message?: string;
      }
    >({
      query: (body) => ({
        url: "/institution/course-requests",
        method: "POST",
        body,
      }),
      invalidatesTags: ["CourseRequestList", "CourseRequest"],
    }),

    acceptQuotation: build.mutation<InstitutionalPurchaseRequest, string>({
      query: (id) => ({
        url: `/institution/course-requests/${id}/accept`,
        method: "POST",
      }),
      invalidatesTags: ["CourseRequestList", "CourseRequest"],
    }),

    requestModification: build.mutation<InstitutionalPurchaseRequest, { id: string; notes: string }>({
      query: ({ id, notes }) => ({
        url: `/institution/course-requests/${id}/request-modification`,
        method: "POST",
        body: { notes },
      }),
      invalidatesTags: ["CourseRequestList", "CourseRequest"],
    }),

    rejectQuotation: build.mutation<InstitutionalPurchaseRequest, { id: string; reason?: string }>({
      query: ({ id, reason }) => ({
        url: `/institution/course-requests/${id}/reject`,
        method: "POST",
        body: { reason },
      }),
      invalidatesTags: ["CourseRequestList", "CourseRequest"],
    }),

    checkoutInstitutionalRequest: build.mutation<
      { provider: string; key_id?: string; order_id: string; amount: number; currency: string; seller_name: string; request_id: string },
      string
    >({
      query: (id) => ({
        url: `/institution/course-requests/${id}/checkout`,
        method: "POST",
      }),
    }),

    verifyPayment: build.mutation<
      InstitutionalPurchaseRequest,
      { id: string; razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }
    >({
      query: ({ id, ...body }) => ({
        url: `/institution/course-requests/${id}/verify-payment`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["CourseRequestList", "CourseRequest"],
    }),

    testCompletePayment: build.mutation<InstitutionalPurchaseRequest, { id: string; payment_method?: string }>({
      query: ({ id, payment_method = "upi_test" }) => ({
        url: `/institution/course-requests/${id}/test-payment`,
        method: "POST",
        body: { payment_method },
      }),
      invalidatesTags: ["CourseRequestList", "CourseRequest", "SubscriptionList"],
    }),

    getInstitutionPurchases: build.query<InstitutionalPackage[], void>({
      query: () => "/institution/purchases",
      transformResponse: (r: { items?: InstitutionalPackage[]; packages?: InstitutionalPackage[] }) =>
        r.items || r.packages || [],
      providesTags: ["SubscriptionList"],
    }),

    getInstitutionPurchaseStudents: build.query<StudentSeatUsage[], string>({
      query: (packageId) => `/institution/purchases/${packageId}/students`,
      transformResponse: (r: { items?: StudentSeatUsage[]; students?: StudentSeatUsage[] }) =>
        r.items || r.students || [],
      providesTags: ["Subscription"],
    }),

    renewPackage: build.mutation<InstitutionalPackage, { id: string; duration_days?: number }>({
      query: ({ id, duration_days = 180 }) => ({
        url: `/institution/purchases/${id}/renew?duration_days=${duration_days}`,
        method: "POST",
      }),
      invalidatesTags: ["SubscriptionList"],
    }),

    // Admin Endpoints
    getAdminInstitutionalRequests: build.query<InstitutionalPurchaseRequest[], { status?: string } | void>({
      query: (params) => ({
        url: "/admin/institutional-requests",
        params: params || {},
      }),
      transformResponse: (r: { items?: InstitutionalPurchaseRequest[]; requests?: InstitutionalPurchaseRequest[] }) =>
        r.items || r.requests || [],
      providesTags: ["CourseRequestList"],
    }),

    getAdminInstitutionalRequestDetail: build.query<InstitutionalPurchaseRequest, string>({
      query: (id) => `/admin/institutional-requests/${id}`,
      transformResponse: (r: { request: InstitutionalPurchaseRequest }) => r.request,
      providesTags: ["CourseRequest"],
    }),

    createAdminQuotation: build.mutation<
      InstitutionalPurchaseRequest,
      {
        id: string;
        course_prices: Array<{ course_id: number | string; course_title: string; unit_price_paise: number }>;
        subtotal_paise: number;
        discount_paise: number;
        discount_note?: string;
        tax_rate_percent: number;
        tax_paise: number;
        total_paise: number;
        approved_seats: number;
        approved_duration_days: number;
        package_starts_at?: string;
        package_ends_at?: string;
        notes?: string;
        valid_days?: number;
      }
    >({
      query: ({ id, ...body }) => ({
        url: `/admin/institutional-requests/${id}/quotation`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["CourseRequestList", "CourseRequest"],
    }),

    approveAndActivatePackage: build.mutation<InstitutionalPurchaseRequest, string>({
      query: (id) => ({
        url: `/admin/institutional-requests/${id}/approve`,
        method: "POST",
      }),
      invalidatesTags: ["CourseRequestList", "CourseRequest", "Subscription", "SubscriptionList"],
    }),

    getAdminInstitutionalPackages: build.query<InstitutionalPackage[], void>({
      query: () => "/admin/institutional-packages",
      transformResponse: (r: { items?: InstitutionalPackage[]; packages?: InstitutionalPackage[] }) =>
        r.items || r.packages || [],
      providesTags: ["SubscriptionList"],
    }),

    getAdminCoursePricing: build.query<CoursePricingItem[], void>({
      query: () => "/admin/course-pricing",
      transformResponse: (r: { items?: CoursePricingItem[]; course_pricing?: CoursePricingItem[] }) =>
        r.items || r.course_pricing || [],
      providesTags: ["Store"],
    }),

    getAdminCoursePricingSummary: build.query<CoursePricingSummary, void>({
      query: () => "/admin/course-pricing/summary",
      providesTags: ["Store"],
    }),

    updateAdminCoursePricing: build.mutation<
      CoursePricingItem,
      {
        course_id: string | number;
        course_title?: string;
        course_code?: string;
        category?: string;
        individual_price_paise: number;
        pricing_method: "fixed" | "monthly" | "hourly";
        fixed_price_paise: number;
        monthly_price_paise: number;
        monthly_billing_rule?: "pro_rata" | "round_up";
        hourly_price_paise: number;
        billable_hours?: number;
        bulk_discount_tiers?: Array<{
          min_students: number;
          max_students: number | null;
          discount_percent: number;
          fixed_discount_paise: number;
        }>;
        gst_percent?: number;
        min_students?: number;
        max_students?: number;
        min_duration_days?: number;
        max_duration_days?: number;
        is_active?: boolean;
        original_price_paise?: number;
        discount_paise?: number;
        discount_type?: "none" | "percentage" | "fixed";
        discount_percent?: number;
        discount_value?: number;
        valid_days?: number;
        reason?: string;
        admin_name?: string;
        admin_role?: string;
      }
    >({
      query: ({ course_id, ...body }) => ({
        url: `/admin/course-pricing/${course_id}`,
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Store"],
    }),

    getAdminCoursePricingAudits: build.query<
      CoursePricingAuditItem[],
      string | number | void
    >({
      query: (courseId) =>
        courseId ? `/admin/course-pricing/${courseId}/audits` : "/admin/course-pricing-audits",
      transformResponse: (r: { audits?: CoursePricingAuditItem[] }) => r.audits || [],
      providesTags: ["Store"],
    }),

    getCoursePricingHistory: build.query<
      CoursePricingHistoryResponse,
      CoursePricingHistoryParams | void
    >({
      query: (params) => ({
        url: "/admin/course-pricing/history",
        params: params || {},
      }),
      providesTags: ["Store"],
    }),
  }),
});

export const {
  useGetInstitutionRequestsQuery,
  useGetInstitutionRequestDetailQuery,
  useGetInstitutionCoursePricingQuery,
  useCalculateInstitutionalPurchaseMutation,
  useSubmitInstitutionRequestMutation,
  useAcceptQuotationMutation,
  useRequestModificationMutation,
  useRejectQuotationMutation,
  useCheckoutInstitutionalRequestMutation,
  useVerifyPaymentMutation,
  useTestCompletePaymentMutation,
  useGetInstitutionPurchasesQuery,
  useGetInstitutionPurchaseStudentsQuery,
  useRenewPackageMutation,
  useGetAdminInstitutionalRequestsQuery,
  useGetAdminInstitutionalRequestDetailQuery,
  useCreateAdminQuotationMutation,
  useApproveAndActivatePackageMutation,
  useGetAdminInstitutionalPackagesQuery,
  useGetAdminCoursePricingQuery,
  useGetAdminCoursePricingSummaryQuery,
  useUpdateAdminCoursePricingMutation,
  useGetAdminCoursePricingAuditsQuery,
  useGetCoursePricingHistoryQuery,
} = institutionalApi;
