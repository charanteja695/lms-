import { baseApi } from "@/core/api/baseApi";
import type { PageContext } from "@/core/api/types";
import { buildQueryString } from "@/core/lib/query";
import type {
  BrowseCourseItem,
  CheckoutSummary,
  GatewayCheckoutPayload,
  InstitutionCheckoutSummary,
  InstitutionStudentItem,
  PaymentActionType,
  PaymentMethodChoice,
  PaymentReceipt,
  PaymentSettings,
  StudentAccountContext,
  StudentPaymentAllocationRecord,
  StudentPaymentRequestRecord,
  StudentPaymentTransaction,
  StudentSubscriptionOverview,
  StudentSubscriptionRecord,
  SubscriptionPlan,
  TransactionFilters,
  TransactionListResult,
} from "@/modules/store/studentTypes";

export const studentSubscriptionsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    browsePublishedCourses: build.query<
      { courses: BrowseCourseItem[]; page_context: PageContext },
      { page?: number; per_page?: number; search_text?: string }
    >({
      query: (params) => `/courses/browse?${buildQueryString(params)}`,
      providesTags: ["BrowseCourseList", "StudentSubscription", "EnrollmentList"],
    }),
    getStudentPlans: build.query<SubscriptionPlan[], void>({
      query: () => "/student/plans",
      transformResponse: (r: { plans: SubscriptionPlan[] }) => r.plans,
      providesTags: ["SubscriptionPlan"],
    }),
    getStudentPaymentSettings: build.query<PaymentSettings, void>({
      query: () => "/student/payment-settings",
      transformResponse: (r: { settings: PaymentSettings }) => r.settings,
      providesTags: ["PaymentSettings"],
    }),
    previewStudentCheckout: build.mutation<
      CheckoutSummary,
      { plan_id: string; course_id?: string | null; action_type?: PaymentActionType }
    >({
      query: (body) => ({ url: "/student/checkout/preview", method: "POST", body }),
      transformResponse: (r: { summary: CheckoutSummary }) => r.summary,
    }),
    createStudentCheckout: build.mutation<
      { transaction: StudentPaymentTransaction; checkout: GatewayCheckoutPayload },
      {
        plan_id: string;
        course_id?: string | null;
        payment_method: PaymentMethodChoice;
        action_type?: PaymentActionType;
        student_name?: string | null;
        student_email?: string | null;
      }
    >({
      query: (body) => ({ url: "/student/checkout", method: "POST", body }),
      transformResponse: (r: { transaction: StudentPaymentTransaction; checkout: GatewayCheckoutPayload }) => ({
        transaction: r.transaction,
        checkout: r.checkout,
      }),
      invalidatesTags: ["StudentTransaction"],
    }),
    verifyStudentPayment: build.mutation<
      { transaction: StudentPaymentTransaction; subscription: StudentSubscriptionRecord | null },
      {
        txId: string;
        razorpay_order_id: string;
        razorpay_payment_id?: string | null;
        razorpay_signature?: string | null;
        outcome?: "succeeded" | "failed" | "pending";
        failure_reason?: string | null;
      }
    >({
      query: ({ txId, ...body }) => ({ url: `/student/payments/${txId}/verify`, method: "POST", body }),
      transformResponse: (r: { transaction: StudentPaymentTransaction; subscription: StudentSubscriptionRecord | null }) => ({
        transaction: r.transaction,
        subscription: r.subscription,
      }),
      invalidatesTags: ["StudentSubscription", "StudentTransaction", "BrowseCourseList", "Enrollment", "EnrollmentList"],
    }),
    triggerTestGatewayCallback: build.mutation<
      { transaction: StudentPaymentTransaction; subscription: StudentSubscriptionRecord | null },
      { txId: string; outcome: "captured" | "failed"; payment_id?: string | null; failure_reason?: string | null }
    >({
      query: ({ txId, ...body }) => ({ url: `/student/payments/${txId}/test-callback`, method: "POST", body }),
      transformResponse: (r: { transaction: StudentPaymentTransaction; subscription: StudentSubscriptionRecord | null }) => ({
        transaction: r.transaction,
        subscription: r.subscription,
      }),
      invalidatesTags: ["StudentSubscription", "StudentTransaction", "BrowseCourseList", "Enrollment", "EnrollmentList"],
    }),
    getStudentPaymentStatus: build.query<
      { transaction: StudentPaymentTransaction; subscription: StudentSubscriptionRecord | null },
      string
    >({
      query: (txId) => `/student/payments/${txId}/status`,
      transformResponse: (r: { transaction: StudentPaymentTransaction; subscription: StudentSubscriptionRecord | null }) => ({
        transaction: r.transaction,
        subscription: r.subscription,
      }),
      providesTags: ["StudentTransaction", "StudentSubscription"],
    }),
    getStudentPaymentHistory: build.query<TransactionListResult, TransactionFilters | void>({
      query: (filters) => `/student/payments?${buildQueryString({ ...(filters ?? {}) })}`,
      providesTags: ["StudentTransaction"],
    }),
    getStudentPaymentReceipt: build.query<PaymentReceipt, string>({
      query: (txId) => `/student/payments/${txId}/receipt`,
      transformResponse: (r: { receipt: PaymentReceipt }) => r.receipt,
    }),
    getStudentSubscriptionOverview: build.query<StudentSubscriptionOverview, void>({
      query: () => "/student/subscription",
      providesTags: ["StudentSubscription", "StudentTransaction"],
    }),
    enrollCourseUnderPlan: build.mutation<StudentSubscriptionOverview, { course_id: string }>({
      query: (body) => ({ url: "/student/subscription/enroll-course", method: "POST", body }),
      invalidatesTags: ["StudentSubscription", "BrowseCourseList", "Enrollment", "EnrollmentList"],
    }),
    getStudentAccountContext: build.query<StudentAccountContext, void>({
      query: () => "/student/account-context",
      transformResponse: (r: StudentAccountContext) => r,
    }),
    createStudentPaymentRequest: build.mutation<
      StudentPaymentRequestRecord,
      { course_id: string; plan_id: string; student_note?: string }
    >({
      query: (body) => ({ url: "/student/payment-requests", method: "POST", body }),
      transformResponse: (r: { payment_request: StudentPaymentRequestRecord }) => r.payment_request,
      invalidatesTags: ["StudentPaymentRequest"],
    }),
    getStudentPaymentRequests: build.query<
      { requests: StudentPaymentRequestRecord[]; page_context: PageContext },
      { status?: string; page?: number; per_page?: number } | void
    >({
      query: (params) => `/student/payment-requests?${buildQueryString({ ...(params ?? {}) })}`,
      providesTags: ["StudentPaymentRequest"],
    }),
    cancelStudentPaymentRequest: build.mutation<StudentPaymentRequestRecord, string>({
      query: (requestId) => ({ url: `/student/payment-requests/${requestId}/cancel`, method: "POST" }),
      transformResponse: (r: { payment_request: StudentPaymentRequestRecord }) => r.payment_request,
      invalidatesTags: ["StudentPaymentRequest"],
    }),
    getInstitutionStudents: build.query<
      {
        students: InstitutionStudentItem[];
        approved_courses: { course_id: number; course_title: string }[];
        page_context: PageContext;
      },
      { search?: string; page?: number; per_page?: number } | void
    >({
      query: (params) => `/institution/payments/students?${buildQueryString({ ...(params ?? {}) })}`,
      providesTags: ["InstitutionPayment", "StudentPaymentRequest"],
    }),
    assignInstitutionStudentCourse: build.mutation<
      StudentPaymentRequestRecord,
      { student_user_id: string; course_id: string; plan_id?: string }
    >({
      query: (body) => ({ url: "/institution/payments/students/assign-course", method: "POST", body }),
      transformResponse: (r: { payment_request: StudentPaymentRequestRecord }) => r.payment_request,
      invalidatesTags: ["InstitutionPayment", "StudentPaymentRequest"],
    }),
    getInstitutionPaymentRequests: build.query<
      { requests: StudentPaymentRequestRecord[]; page_context: PageContext },
      { status?: string; search?: string; page?: number; per_page?: number } | void
    >({
      query: (params) => `/institution/payments/requests?${buildQueryString({ ...(params ?? {}) })}`,
      providesTags: ["StudentPaymentRequest", "InstitutionPayment"],
    }),
    approveInstitutionRequest: build.mutation<StudentPaymentRequestRecord, { requestId: string; decision_note?: string }>({
      query: ({ requestId, decision_note }) => ({
        url: `/institution/payments/requests/${requestId}/approve`,
        method: "POST",
        body: { decision_note },
      }),
      transformResponse: (r: { payment_request: StudentPaymentRequestRecord }) => r.payment_request,
      invalidatesTags: ["StudentPaymentRequest", "InstitutionPayment"],
    }),
    rejectInstitutionRequest: build.mutation<StudentPaymentRequestRecord, { requestId: string; decision_note?: string }>({
      query: ({ requestId, decision_note }) => ({
        url: `/institution/payments/requests/${requestId}/reject`,
        method: "POST",
        body: { decision_note },
      }),
      transformResponse: (r: { payment_request: StudentPaymentRequestRecord }) => r.payment_request,
      invalidatesTags: ["StudentPaymentRequest", "InstitutionPayment"],
    }),
    previewInstitutionCheckout: build.mutation<
      InstitutionCheckoutSummary,
      { student_ids: string[]; plan_id: string; course_id?: string; request_ids?: string[] }
    >({
      query: (body) => ({ url: "/institution/payments/checkout/preview", method: "POST", body }),
      transformResponse: (r: { summary: InstitutionCheckoutSummary }) => r.summary,
    }),
    createInstitutionCheckout: build.mutation<
      {
        transaction: StudentPaymentTransaction;
        allocations: StudentPaymentAllocationRecord[];
        gateway: GatewayCheckoutPayload;
      },
      {
        student_ids: string[];
        plan_id: string;
        payment_method: PaymentMethodChoice;
        course_id?: string;
        request_ids?: string[];
      }
    >({
      query: (body) => ({ url: "/institution/payments/checkout", method: "POST", body }),
      invalidatesTags: ["InstitutionPayment", "StudentPaymentRequest"],
    }),
    verifyInstitutionPayment: build.mutation<
      { transaction: StudentPaymentTransaction; allocations: StudentPaymentAllocationRecord[] },
      {
        txId: string;
        razorpay_order_id?: string;
        razorpay_payment_id?: string;
        razorpay_signature?: string;
        outcome: "succeeded" | "failed" | "pending";
        failure_reason?: string;
      }
    >({
      query: ({ txId, ...body }) => ({ url: `/institution/payments/transactions/${txId}/verify`, method: "POST", body }),
      invalidatesTags: ["InstitutionPayment", "StudentPaymentRequest", "StudentSubscription", "StudentTransaction"],
    }),
    triggerInstitutionTestCallback: build.mutation<
      { transaction: StudentPaymentTransaction; allocations: StudentPaymentAllocationRecord[] },
      { txId: string; outcome: "captured" | "failed"; payment_id?: string; failure_reason?: string }
    >({
      query: ({ txId, ...body }) => ({ url: `/institution/payments/transactions/${txId}/test-callback`, method: "POST", body }),
      invalidatesTags: ["InstitutionPayment", "StudentPaymentRequest", "StudentSubscription", "StudentTransaction"],
    }),
    getInstitutionTransactions: build.query<
      TransactionListResult,
      { status?: string; page?: number; per_page?: number } | void
    >({
      query: (params) => `/institution/payments/transactions?${buildQueryString({ ...(params ?? {}) })}`,
      providesTags: ["InstitutionPayment"],
    }),
    getInstitutionAllocations: build.query<
      { allocations: StudentPaymentAllocationRecord[]; page_context: PageContext },
      { student_user_id?: string; page?: number; per_page?: number } | void
    >({
      query: (params) => `/institution/payments/allocations?${buildQueryString({ ...(params ?? {}) })}`,
      providesTags: ["InstitutionPayment"],
    }),
  }),
});

export const {
  useBrowsePublishedCoursesQuery,
  useGetStudentPlansQuery,
  useGetStudentPaymentSettingsQuery,
  usePreviewStudentCheckoutMutation,
  useCreateStudentCheckoutMutation,
  useVerifyStudentPaymentMutation,
  useTriggerTestGatewayCallbackMutation,
  useGetStudentPaymentStatusQuery,
  useGetStudentPaymentHistoryQuery,
  useLazyGetStudentPaymentReceiptQuery,
  useGetStudentSubscriptionOverviewQuery,
  useEnrollCourseUnderPlanMutation,
  useGetStudentAccountContextQuery,
  useCreateStudentPaymentRequestMutation,
  useGetStudentPaymentRequestsQuery,
  useCancelStudentPaymentRequestMutation,
  useGetInstitutionStudentsQuery,
  useAssignInstitutionStudentCourseMutation,
  useGetInstitutionPaymentRequestsQuery,
  useApproveInstitutionRequestMutation,
  useRejectInstitutionRequestMutation,
  usePreviewInstitutionCheckoutMutation,
  useCreateInstitutionCheckoutMutation,
  useVerifyInstitutionPaymentMutation,
  useTriggerInstitutionTestCallbackMutation,
  useGetInstitutionTransactionsQuery,
  useGetInstitutionAllocationsQuery,
} = studentSubscriptionsApi;
