import { Navigate, useNavigate } from "react-router-dom";

import { useAppDispatch } from "@/app/hooks";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { MfaSetup } from "@/modules/user-management/account/components/mfa/MfaSetup";
import { SetupShell } from "@/modules/user-management/account/components/SetupShell";
import { userFlagsChanged } from "@/modules/user-management/auth/store/authSlice";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Card } from "@/shared/ui";

/** Shown to roles where two-factor authentication is mandatory until they enrol. */
export function MfaSetupRequiredPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAuth();

  if (user && !user.mfa_setup_required) {
    return <Navigate to="/" replace />;
  }
  return (
    <SetupShell>
      <AuthCard title="Protect your account" description="Two-factor authentication is required for your role. It takes about a minute.">
        <Card>
          <MfaSetup
            onFinished={() => {
              dispatch(userFlagsChanged({ mfa_setup_required: false, mfa_enabled: true }));
              navigate("/", { replace: true });
            }}
          />
        </Card>
      </AuthCard>
    </SetupShell>
  );
}
