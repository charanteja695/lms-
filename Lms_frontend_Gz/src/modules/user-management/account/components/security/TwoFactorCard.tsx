import { useState } from "react";

import { useAppDispatch } from "@/app/hooks";
import { MfaSetup } from "@/modules/user-management/account/components/mfa/MfaSetup";
import { RecoveryCodes } from "@/modules/user-management/account/components/mfa/RecoveryCodes";
import { PasswordAndCodeModal } from "@/modules/user-management/account/components/security/PasswordAndCodeModal";
import { useGetMfaStatusQuery } from "@/modules/user-management/auth/api/authApi";
import { userFlagsChanged } from "@/modules/user-management/auth/store/authSlice";
import { Badge, Button, Card, PageLoader } from "@/shared/ui";

export function TwoFactorCard() {
  const { data: status, isLoading } = useGetMfaStatusQuery();
  const dispatch = useAppDispatch();
  const [mode, setMode] = useState<"idle" | "setup" | "disable" | "codes">("idle");
  const [newCodes, setNewCodes] = useState<string[] | null>(null);

  return (
    <Card
      title="Two-factor authentication"
      description="A code from your phone is required after your password."
      actions={status && <Badge tone={status.enabled ? "green" : "gray"}>{status.enabled ? "On" : "Off"}</Badge>}
    >
      {isLoading || !status ? (
        <PageLoader />
      ) : mode === "setup" ? (
        <MfaSetup
          onFinished={() => {
            dispatch(userFlagsChanged({ mfa_enabled: true, mfa_setup_required: false }));
            setMode("idle");
          }}
        />
      ) : newCodes ? (
        <RecoveryCodes codes={newCodes} onDone={() => setNewCodes(null)} />
      ) : status.enabled ? (
        <div className="flex flex-wrap items-center gap-3">
          <p className="mr-auto text-sm text-slate-600">
            {status.recovery_codes_remaining} recovery code{status.recovery_codes_remaining === 1 ? "" : "s"} left.
            {status.required && " Required for your role."}
          </p>
          <Button variant="secondary" icon="refresh" onClick={() => setMode("codes")}>
            New recovery codes
          </Button>
          {!status.required && (
            <Button variant="danger" onClick={() => setMode("disable")}>
              Turn off
            </Button>
          )}
        </div>
      ) : (
        <Button icon="shield" onClick={() => setMode("setup")}>
          Set up two-factor authentication
        </Button>
      )}

      <PasswordAndCodeModal
        open={mode === "disable" || mode === "codes"}
        purpose={mode === "disable" ? "disable" : "codes"}
        onClose={() => setMode("idle")}
        onCodes={(codes) => {
          setNewCodes(codes);
          setMode("idle");
        }}
        onDisabled={() => {
          dispatch(userFlagsChanged({ mfa_enabled: false }));
          setMode("idle");
        }}
      />
    </Card>
  );
}
