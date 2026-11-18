import { baseApi } from "@/core/api/baseApi";
import { buildQueryString } from "@/core/lib/query";
import type {
  AdminPaymentReports,
  AssessmentAccessRules,
  CertificateLevel,
  CourseAccessRules,
  PaymentSettings,
  SubscriptionPlan,
  TransactionFilters,
  TransactionListResult,
} from "@/modules/store/studentTypes";

export interface PlanUpsertInput {
  code: string;
  name: string;
  description: string;
  price_paise: number;
  min_price_paise: number | null;
  max_price_paise: number | null;
  billing_duration_days: number;
  billing_label: string;
  max_courses: number | null;
  clear_max_courses?: boolean;
  features: string[];
  course_access_rules: CourseAccessRules;
  assessment_access: AssessmentAccessRules;
  certificate_level: CertificateLevel;
  support_tier: string;
  is_active: boolean;
  is_recommended: boolean;
  display_order: number;
  tier_rank: number;
}

export interface PaymentSettingsInput {
  payments_enabled: boolean;
  min_amount_paise: number;
  max_amount_paise: number;
  accepted_methods: Record<string, boolean>;
  tax_rate_percent: number;
  upgrade_pricing_mode: "price_difference" | "full_price";
  upi_vpa: string;
  upi_merchant_name: string;
}

export const studentPlansAdminApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    adminListSubscriptionPlans: build.query<SubscriptionPlan[], void>({
      query: () => "/admin/subscription-plans",
      transformResponse: (r: { plans: SubscriptionPlan[] }) => r.plans,
      providesTags: ["SubscriptionPlan"],
    }),
    adminCreateSubscriptionPlan: build.mutation<SubscriptionPlan, PlanUpsertInput>({
      query: (body) => ({ url: "/admin/subscription-plans", method: "POST", body }),
      transformResponse: (r: { plan: SubscriptionPlan }) => r.plan,
      invalidatesTags: ["SubscriptionPlan", "BrowseCourseList"],
    }),
    adminUpdateSubscriptionPlan: build.mutation<SubscriptionPlan, { planId: string } & Partial<PlanUpsertInput>>({
      query: ({ planId, ...body }) => ({ url: `/admin/subscription-plans/${planId}`, method: "PATCH", body }),
      transformResponse: (r: { plan: SubscriptionPlan }) => r.plan,
      invalidatesTags: ["SubscriptionPlan", "BrowseCourseList", "StudentSubscription"],
    }),
    adminDeleteSubscriptionPlan: build.mutation<void, string>({
      query: (planId) => ({ url: `/admin/subscription-plans/${planId}`, method: "DELETE" }),
      invalidatesTags: ["SubscriptionPlan", "BrowseCourseList"],
    }),
    adminGetPaymentSettings: build.query<PaymentSettings, void>({
      query: () => "/admin/payment-settings",
      transformResponse: (r: { settings: PaymentSettings }) => r.settings,
      providesTags: ["PaymentSettings"],
    }),
    adminUpdatePaymentSettings: build.mutation<PaymentSettings, PaymentSettingsInput>({
      query: (body) => ({ url: "/admin/payment-settings", method: "PUT", body }),
      transformResponse: (r: { settings: PaymentSettings }) => r.settings,
      invalidatesTags: ["PaymentSettings", "BrowseCourseList"],
    }),
    adminListTransactions: build.query<TransactionListResult, TransactionFilters | void>({
      query: (filters) => `/admin/transactions?${buildQueryString({ ...(filters ?? {}) })}`,
      providesTags: ["StudentTransaction"],
    }),
    adminGetPaymentReports: build.query<AdminPaymentReports, void>({
      query: () => "/admin/payment-reports",
      providesTags: ["StudentTransaction", "StudentSubscription"],
    }),
  }),
});

export const {
  useAdminListSubscriptionPlansQuery,
  useAdminCreateSubscriptionPlanMutation,
  useAdminUpdateSubscriptionPlanMutation,
  useAdminDeleteSubscriptionPlanMutation,
  useAdminGetPaymentSettingsQuery,
  useAdminUpdatePaymentSettingsMutation,
  useAdminListTransactionsQuery,
  useAdminGetPaymentReportsQuery,
} = studentPlansAdminApi;
