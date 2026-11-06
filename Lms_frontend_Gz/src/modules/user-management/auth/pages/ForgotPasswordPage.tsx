import { useState } from "react";

import { IdentifierStep } from "@/modules/user-management/auth/components/IdentifierStep";
import { NewPasswordForm } from "@/modules/user-management/auth/components/NewPasswordForm";
import { OtpStep } from "@/modules/user-management/auth/components/OtpStep";

type Step = "identifier" | "otp" | "password";

/** Forgot password: identifier → emailed code → new password. */
export function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>("identifier");
  const [identifier, setIdentifier] = useState("");
  const [resetToken, setResetToken] = useState("");

  if (step === "identifier") {
    return <IdentifierStep onSent={(value) => { setIdentifier(value); setStep("otp"); }} />;
  }
  if (step === "otp") {
    return <OtpStep identifier={identifier} onVerified={(token) => { setResetToken(token); setStep("password"); }} onBack={() => setStep("identifier")} />;
  }
  return <NewPasswordForm resetToken={resetToken} title="Choose a new password" onInvalidToken={() => setStep("identifier")} />;
}
