import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAppDispatch } from "@/app/hooks";
import { SignupCodeStep } from "@/modules/user-management/auth/components/signup/SignupCodeStep";
import { SignupDetailsStep, type SignupValues } from "@/modules/user-management/auth/components/signup/SignupDetailsStep";
import { credentialsReceived } from "@/modules/user-management/auth/store/authSlice";
import type { LoginResponse } from "@/modules/user-management/auth/types";

/** Self sign-up for individual learners: details, then the emailed code; they land in the course store. */
export function SignupPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const [sent, setSent] = useState<{ values: SignupValues; expiresIn: number } | null>(null);
  const [draft, setDraft] = useState<SignupValues | undefined>();

  const done = (response: LoginResponse) => {
    if (!response.token || !response.user) return;
    dispatch(credentialsReceived({ token: response.token, user: response.user }));  // the guard then opens the store
  };

  return sent ? (
    <SignupCodeStep values={sent.values} expiresIn={sent.expiresIn} onDone={done} onBack={() => { setDraft(sent.values); setSent(null); }} />
  ) : (
    <SignupDetailsStep
      initial={draft}
      onSent={(values, expiresIn) => {
        setSent({ values, expiresIn });
        navigate("/register", { replace: true, state: { from: "/store" } });  // where the signed-out-only guard sends them once in
      }}
    />
  );
}
