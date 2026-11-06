import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { toApiError } from "@/core/lib/apiError";
import { useLoginMutation } from "@/modules/user-management/auth/api/authApi";
import { MfaStep } from "@/modules/user-management/auth/components/MfaChallengeForm";
import { credentialsReceived, mfaChallengeCleared, mfaChallengeReceived } from "@/modules/user-management/auth/store/authSlice";
import type { LoginResponse } from "@/modules/user-management/auth/types";
import { PasswordField, TextField } from "@/shared/form";
import { AuthCard } from "@/shared/layout/AuthCard";
import { env } from "@/core/config/env";
import { Alert, Button, Icon } from "@/shared/ui";

interface LoginValues {
  identifier: string;
  password: string;
}

const DEMO_PRESETS = [
  { label: "Default Admin", email: "admin@example.com", password: "Password123!", role: "Admin", mfa: "123456" },
  { label: "Student 3", email: "demo.student3@example.com", password: "Stud3nt!Lms#Demo3", role: "Student", mfa: null },
  { label: "Student 1", email: "demo.student1@example.com", password: "Stud3nt!Lms#Demo1", role: "Student", mfa: null },
  { label: "Student 2", email: "demo.student2@example.com", password: "Stud3nt!Lms#Demo2", role: "Student", mfa: null },
  { label: "Staff 1", email: "demo.staff1@example.com", password: "St4ff!Prof#Demo1", role: "Staff", mfa: null },
  { label: "Staff 2", email: "demo.staff2@example.com", password: "St4ff!Prof#Demo2", role: "Staff", mfa: null },
  { label: "Staff 3", email: "demo.staff3@example.com", password: "St4ff!Prof#Demo3", role: "Staff", mfa: null },
  { label: "Institution Head 1", email: "demo.head1@example.com", password: "H3ad!Inst#Demo1", role: "Head", mfa: null },
  { label: "Institution Head 2", email: "demo.head2@example.com", password: "H3ad!Inst#Demo2", role: "Head", mfa: null },
  { label: "Institution Head 3", email: "demo.head3@example.com", password: "H3ad!Inst#Demo3", role: "Head", mfa: null },
  { label: "Admin 1", email: "demo.admin1@example.com", password: "Adm1n!Demo#Acct1", role: "Admin", mfa: null },
  { label: "Admin 2", email: "demo.admin2@example.com", password: "Adm1n!Demo#Acct2", role: "Admin", mfa: null },
  { label: "Admin 3", email: "demo.admin3@example.com", password: "Adm1n!Demo#Acct3", role: "Admin", mfa: null },
  { label: "Super Admin 1", email: "demo.superadmin1@example.com", password: "Sup3r!Admin#Demo1", role: "Super Admin", mfa: null },
  { label: "Super Admin 2", email: "demo.superadmin2@example.com", password: "Sup3r!Admin#Demo2", role: "Super Admin", mfa: null },
  { label: "Super Admin 3", email: "demo.superadmin3@example.com", password: "Sup3r!Admin#Demo3", role: "Super Admin", mfa: null },
];

export function LoginPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const challenge = useAppSelector((state) => state.auth.mfaChallenge);
  const [login, { isLoading }] = useLoginMutation();
  const [formError, setFormError] = useState<string | null>(null);
  const [selectedDemoIndex, setSelectedDemoIndex] = useState(0);
  const form = useForm<LoginValues>({ defaultValues: { identifier: "", password: "" } });

  const activeDemo = DEMO_PRESETS[selectedDemoIndex] ?? (DEMO_PRESETS[0] as (typeof DEMO_PRESETS)[number]);

  const applyDemo = (index: number) => {
    setSelectedDemoIndex(index);
    const demo = DEMO_PRESETS[index];
    if (demo) {
      form.setValue("identifier", demo.email);
      form.setValue("password", demo.password);
      setFormError(null);
    }
  };

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";

  const finish = (response: LoginResponse) => {
    if (response.token && response.user) {
      dispatch(credentialsReceived({ token: response.token, user: response.user }));
      if (response.user.must_change_password) {
        navigate("/account/setup/password", { replace: true });
      } else if (response.user.mfa_setup_required) {
        navigate("/account/setup/mfa", { replace: true });
      } else {
        navigate(redirectTo, { replace: true });
      }
    }
  };

  const onSubmit = form.handleSubmit(async (values) => {
    setFormError(null);
    try {
      const response = await login(values).unwrap();
      if (response.code === "MFA_REQUIRED" && response.mfa_challenge) {
        dispatch(mfaChallengeReceived({ challenge: response.mfa_challenge, identifier: values.identifier }));
        return;
      }
      finish(response);
    } catch (error) {
      setFormError(toApiError(error).message);
      form.resetField("password");
    }
  });

  if (challenge) return <MfaStep onDone={finish} onCancel={() => dispatch(mfaChallengeCleared())} />;

  return (
    <AuthCard
      title="Welcome back"
      description={`Sign in to ${env.appName} with your email address or username.`}
      footer={
        <>
          New here?{" "}
          <Link to="/register" className="font-semibold text-brand-700 underline-offset-4 hover:underline">Create an account</Link> to buy courses.
          <span className="mt-1 block text-xs text-slate-500">Studying with an institution? It creates your account for you.</span>
        </>
      }
    >
      <FormProvider {...form}>
        <form onSubmit={onSubmit} className="space-y-5" noValidate>
          {formError && <Alert tone="error">{formError}</Alert>}
          
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3.5 text-xs text-slate-700">
            <div className="mb-2 flex items-center justify-between font-bold text-emerald-950">
              <span className="flex items-center gap-1.5">
                <Icon name="user" size={14} className="text-emerald-700" />
                Demo Credentials Helper
              </span>
              <button
                type="button"
                onClick={() => applyDemo(selectedDemoIndex)}
                className="font-bold text-emerald-800 underline decoration-emerald-500 hover:text-emerald-950"
              >
                Auto-fill
              </button>
            </div>

            <div className="mb-2">
              <label htmlFor="demo-account-select" className="sr-only">Choose Demo Account</label>
              <select
                id="demo-account-select"
                value={selectedDemoIndex}
                onChange={(e) => applyDemo(Number(e.target.value))}
                className="w-full rounded-lg border border-emerald-300 bg-white px-2 py-1.5 text-xs font-medium text-emerald-950 focus:border-emerald-500 focus:outline-none"
              >
                {DEMO_PRESETS.map((preset, idx) => (
                  <option key={preset.email} value={idx}>
                    [{preset.role}] {preset.label} — {preset.email}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-0.5">
              <div>Email: <code className="font-mono font-bold text-emerald-900">{activeDemo.email}</code></div>
              <div>Password: <code className="font-mono font-bold text-emerald-900">{activeDemo.password}</code></div>
              {activeDemo.mfa && (
                <div className="mt-1 text-[11px] text-emerald-800/80">
                  2FA verification code: <code className="font-mono font-bold text-emerald-900">{activeDemo.mfa}</code>
                </div>
              )}
            </div>
          </div>

          <TextField<LoginValues> name="identifier" label="Email or username" autoComplete="username" required />
          <PasswordField<LoginValues> name="password" label="Password" required />
          <div className="-mt-1 flex justify-end">
            <Link to="/forgot-password" className="rounded text-sm font-semibold text-brand-700 underline-offset-4 hover:underline">
              Forgot password?
            </Link>
          </div>
          <Button type="submit" fullWidth size="lg" loading={isLoading}>
            Sign in
          </Button>
          <p className="flex items-center justify-center gap-1.5 text-xs text-slate-500">
            <Icon name="shield" size={14} className="text-brand-600" />
            Your connection is encrypted
          </p>
        </form>
      </FormProvider>
    </AuthCard>
  );
}
