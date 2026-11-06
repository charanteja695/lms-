import { useState } from "react";

import { PasswordStep } from "@/modules/user-management/account/components/mfa/MfaPasswordStep";
import { ScanStep } from "@/modules/user-management/account/components/mfa/MfaScanStep";
import { RecoveryCodes } from "@/modules/user-management/account/components/mfa/RecoveryCodes";

type Step = { name: "password" } | { name: "scan"; secret: string; uri: string } | { name: "codes"; codes: string[] };

/** Password → scan QR → confirm code → save recovery codes. */
export function MfaSetup({ onFinished }: { onFinished: () => void }) {
  const [step, setStep] = useState<Step>({ name: "password" });
  if (step.name === "password") return <PasswordStep onStarted={(secret, uri) => setStep({ name: "scan", secret, uri })} />;
  if (step.name === "scan") return <ScanStep secret={step.secret} uri={step.uri} onEnabled={(codes) => setStep({ name: "codes", codes })} />;
  return <RecoveryCodes codes={step.codes} onDone={onFinished} />;
}
