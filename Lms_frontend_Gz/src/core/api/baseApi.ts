import { createApi, fetchBaseQuery, type BaseQueryApi, type BaseQueryFn, type FetchArgs, type FetchBaseQueryError } from "@reduxjs/toolkit/query/react";

import { env } from "@/core/config/env";
import { toApiError } from "@/core/lib/apiError";
import { buildQueryString } from "@/core/lib/query";
import { credentialsReceived, loggedOut, userFlagsChanged } from "@/modules/user-management/auth/store/authSlice";
import type { LoginResponse } from "@/modules/user-management/auth/types";

interface AuthAwareState {
  auth: { accessToken: string | null };
}

/**
 * Browser sessions: the refresh token never reaches JavaScript. This header makes the API set it as an
 * httpOnly cookie and read it back on refresh; it is also the CSRF guard, since a cross-site page cannot send it.
 */
export const SESSION_TRANSPORT = { "X-Session-Transport": "cookie" } as const;

const PUBLIC_AUTH_PATHS = ["/auth/login", "/auth/refresh-token", "/auth/mfa/verify", "/auth/forgot-password", "/auth/verify-otp", "/auth/reset-password"];

export const rawBaseQuery = fetchBaseQuery({
  baseUrl: env.apiBaseUrl,
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as AuthAwareState).auth.accessToken;
    if (token) headers.set("Authorization", `Bearer ${token}`);
    headers.set("Accept", "application/json");
    headers.set("X-Session-Transport", "cookie");
    return headers;
  },
  paramsSerializer: buildQueryString,
});

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Exchange the refresh token for new tokens. Concurrent 401s share one refresh request, which matters
 * because the backend treats a reused refresh token as theft and ends the session.
 */
export function refreshSession(api: Pick<BaseQueryApi, "getState" | "dispatch" | "signal" | "abort" | "extra" | "endpoint" | "type">): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const result = await rawBaseQuery({ url: "/auth/refresh-token", method: "POST" }, api as BaseQueryApi, {});
      const data = result.data as LoginResponse | undefined;
      if (data?.token && data.user) {
        api.dispatch(credentialsReceived({ token: data.token, user: data.user }));
        return true;
      }
      api.dispatch(loggedOut());
      return false;
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const baseQueryWithReauth: BaseQueryFn<string | FetchArgs, unknown, FetchBaseQueryError> = async (args, api, extraOptions) => {
  const url = typeof args === "string" ? args : args.url;
  const method = (typeof args === "string" ? "GET" : args.method || "GET").toUpperCase();
  const isGet = method === "GET";

  let result = await rawBaseQuery(args, api, extraOptions);

  // 1. Silent token refresh on 401 when JWKS/service re-initializes (retry once only, then redirect)
  if (result.error?.status === 401 && !PUBLIC_AUTH_PATHS.some((path) => url.startsWith(path))) {
    const refreshed = await refreshSession(api);
    if (refreshed) {
      result = await rawBaseQuery(args, api, extraOptions);
      if (result.error?.status === 401) {
        api.dispatch(loggedOut());
        if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
          window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`;
        }
      }
    } else {
      api.dispatch(loggedOut());
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`;
      }
    }
  }

  // 2. Auto-retry failed GET queries (2 retries with exponential backoff: 500ms, 1200ms) on transient 502/503/504 or FETCH_ERROR
  if (result.error && (isGet || (extraOptions as any)?.retry)) {
    const status = result.error.status;
    const isTransient = status === 502 || status === 503 || status === 504 || status === "FETCH_ERROR";
    if (isTransient) {
      await wait(500);
      result = await rawBaseQuery(args, api, extraOptions);
      if (result.error) {
        const retryStatus = result.error.status;
        if (retryStatus === 502 || retryStatus === 503 || retryStatus === 504 || retryStatus === "FETCH_ERROR") {
          await wait(1200);
          result = await rawBaseQuery(args, api, extraOptions);
        }
      }
    }
  }

  if (result.error?.status === 403) {
    const { code } = toApiError(result.error);
    // The route guards react to these flags and send the user to the set-up step.
    if (code === "PASSWORD_CHANGE_REQUIRED") api.dispatch(userFlagsChanged({ must_change_password: true }));
    if (code === "MFA_SETUP_REQUIRED") api.dispatch(userFlagsChanged({ mfa_setup_required: true }));
  }
  return result;
};

export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithReauth,
  tagTypes: [
    "Me",
    "MediaLibrary",
    "Store",
    "Permissions",
    "User",
    "UserList",
    "Admin",
    "AdminList",
    "Institution",
    "InstitutionList",
    "Employer",
    "EmployerList",
    "AuditLog",
    "Job",
    "Sessions",
    "Mfa",
    "Course",
    "CourseList",
    "CourseVersion",
    "LearningPath",
    "LearningPathList",
    "CourseRequest",
    "CourseRequestList",
    "Subscription",
    "SubscriptionList",
    "Batch",
    "BatchList",
    "Enrollment",
    "EnrollmentList",
    "UnlockState",
    "LanguageList",
    "Problem",
    "ProblemList",
    "ProblemAuthor",
    "ProblemStats",
    "TestCaseList",
    "SavedCode",
    "Submission",
    "SubmissionList",
    "ReviewSubmission",
    "ReviewSubmissionList",
    "Question",
    "QuestionList",
    "QuestionVersionList",
    "Test",
    "TestList",
    "TestSchedules",
    "TestResults",
    "TestAnalytics",
    "TestPlagiarism",
    "MyTestList",
    "MyTest",
    "Attempt",
    "Academics",
    "SectionStudents",
    "AttemptList",
    "AttemptEvents",
    "AttemptResult",
    "GradingQueue",
    "ProctorSession",
    "ProctorSessionList",
    "ProctorCase",
    "ProctorCaseList",
    "MyProctorCaseList",
    "ProctorMediaAccess",
    "Certificate",
    "CertificateList",
    "CertificateTemplate",
    "CertificateTemplateList",
    "TutorAvailability",
    "TutorConversation",
    "TutorConversationList",
    "TutorFaqList",
    "TutorFeedback",
    "TutorEvalSet",
    "TutorEvalSetList",
    "TutorIndex",
    "TutorEscalationList",
    "SupportTicket",
    "SupportTicketList",
    "SupportSummary",
    "CannedReplyList",
    "SlaPolicies",
    "CareerProfile",
    "Resume",
    "ResumeList",
    "ResumeVersions",
    "JobBoard",
    "JobPreferences",
    "MyApplication",
    "EmployerProfile",
    "EmployerJob",
    "EmployerJobList",
    "JobApplicants",
    "Drive",
    "Placements",
    "JobAdmin",
    "InterviewPlan",
    "InterviewPlanList",
    "MyInterview",
    "MyInterviewList",
    "ScreeningInterview",
    "InterviewAppeals",
    "Calibration",
    "Notifications",
    "UnreadCount",
    "NotificationPreferences",
    "NotificationTemplates",
    "Deliveries",
    "AnalyticsReport",
    "BillingProfile",
    "Prices",
    "Quotes",
    "Invoices",
    "EmployerPlans",
    "PermissionCatalog",
    "RolePermissions",
    "PersonPermissions",
    "AiQuota",
    "AiModels",
    "AiPrompts",
  ],
  // Data is requested only by the screens that show it, cached, and refetched only after a related change.
  keepUnusedDataFor: 60,
  refetchOnMountOrArgChange: false,
  refetchOnFocus: false,
  refetchOnReconnect: true,
  endpoints: () => ({}),
});
