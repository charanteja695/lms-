import { baseApi } from "@/core/api/baseApi";
import type { SuccessEnvelope } from "@/core/api/types";
import type { LoginResponse, MfaStatus, SessionOut } from "@/modules/user-management/auth/types";
import type { User } from "@/modules/user-management/users/types";

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    login: build.mutation<LoginResponse, { identifier: string; password: string }>({
      query: (body) => ({ url: "/auth/login", method: "POST", body }),
    }),
    register: build.mutation<SuccessEnvelope & { signup: { email: string; expires_in: number } }, { first_name: string; last_name: string; email: string; password: string }>({
      query: (body) => ({ url: "/auth/register", method: "POST", body }),
    }),
    registerVerify: build.mutation<LoginResponse, { email: string; code: string }>({
      query: (body) => ({ url: "/auth/register/verify", method: "POST", body }),
    }),
    verifyMfa: build.mutation<LoginResponse, { mfa_token: string; code?: string; recovery_code?: string }>({
      query: (body) => ({ url: "/auth/mfa/verify", method: "POST", body }),
    }),
    logout: build.mutation<SuccessEnvelope, { all_sessions?: boolean } | void>({
      query: (body) => ({ url: "/auth/logout", method: "POST", body: body ?? {} }),
    }),
    forgotPassword: build.mutation<SuccessEnvelope, { identifier: string }>({
      query: (body) => ({ url: "/auth/forgot-password", method: "POST", body }),
    }),
    verifyOtp: build.mutation<SuccessEnvelope & { password_reset: { reset_token: string; expires_in: number } }, { identifier: string; otp: string }>({
      query: (body) => ({ url: "/auth/verify-otp", method: "POST", body }),
    }),
    resetPassword: build.mutation<SuccessEnvelope, { reset_token: string; new_password: string; confirm_password: string }>({
      query: (body) => ({ url: "/auth/reset-password", method: "POST", body }),
    }),
    changePassword: build.mutation<SuccessEnvelope, { current_password: string; new_password: string; confirm_password: string }>({
      query: (body) => ({ url: "/auth/change-password", method: "POST", body }),
    }),

    getMe: build.query<User, void>({
      query: () => "/users/me",
      transformResponse: (response: { user: User }) => response.user,
      providesTags: ["Me"],
    }),
    updateMe: build.mutation<User, Record<string, unknown>>({
      query: (body) => ({ url: "/users/me", method: "PUT", body }),
      transformResponse: (response: { user: User }) => response.user,
      invalidatesTags: ["Me"],
    }),

    listSessions: build.query<SessionOut[], void>({
      query: () => "/auth/sessions",
      transformResponse: (response: { sessions: SessionOut[] }) => response.sessions,
      providesTags: ["Sessions"],
    }),
    endSession: build.mutation<SuccessEnvelope, string>({
      query: (sessionId) => ({ url: `/auth/sessions/${sessionId}`, method: "DELETE" }),
      invalidatesTags: ["Sessions"],
    }),

    getMfaStatus: build.query<MfaStatus, void>({
      query: () => "/auth/mfa",
      transformResponse: (response: { mfa: MfaStatus }) => response.mfa,
      providesTags: ["Mfa"],
    }),
    startMfaSetup: build.mutation<{ secret: string; otpauth_uri: string }, { password: string }>({
      query: (body) => ({ url: "/auth/mfa/setup", method: "POST", body }),
      transformResponse: (response: { mfa_setup: { secret: string; otpauth_uri: string } }) => response.mfa_setup,
    }),
    enableMfa: build.mutation<string[], { code: string }>({
      query: (body) => ({ url: "/auth/mfa/enable", method: "POST", body }),
      transformResponse: (response: { recovery_codes: string[] }) => response.recovery_codes,
      invalidatesTags: ["Mfa"],
    }),
    disableMfa: build.mutation<SuccessEnvelope, { password: string; code: string }>({
      query: (body) => ({ url: "/auth/mfa/disable", method: "POST", body }),
      invalidatesTags: ["Mfa"],
    }),
    regenerateRecoveryCodes: build.mutation<string[], { password: string; code: string }>({
      query: (body) => ({ url: "/auth/mfa/recovery-codes", method: "POST", body }),
      transformResponse: (response: { recovery_codes: string[] }) => response.recovery_codes,
      invalidatesTags: ["Mfa"],
    }),
  }),
});

export const {
  useLoginMutation,
  useRegisterMutation,
  useRegisterVerifyMutation,
  useVerifyMfaMutation,
  useLogoutMutation,
  useForgotPasswordMutation,
  useVerifyOtpMutation,
  useResetPasswordMutation,
  useChangePasswordMutation,
  useGetMeQuery,
  useUpdateMeMutation,
  useListSessionsQuery,
  useEndSessionMutation,
  useGetMfaStatusQuery,
  useStartMfaSetupMutation,
  useEnableMfaMutation,
  useDisableMfaMutation,
  useRegenerateRecoveryCodesMutation,
} = authApi;
