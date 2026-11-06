import { ChangePasswordForm } from "@/modules/user-management/account/components/ChangePasswordForm";
import { SetupShell } from "@/modules/user-management/account/components/SetupShell";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Card } from "@/shared/ui";

/** Shown when an account was created with a temporary password. */
export function PasswordSetupRequiredPage() {
  return (
    <SetupShell>
      <AuthCard title="Choose your own password" description="Your account uses a temporary password. Set a new one to continue.">
        <Card>
          <ChangePasswordForm submitLabel="Save and continue" />
        </Card>
      </AuthCard>
    </SetupShell>
  );
}
