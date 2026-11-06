import { ChangePasswordForm } from "@/modules/user-management/account/components/ChangePasswordForm";
import { SessionsCard } from "@/modules/user-management/account/components/security/SessionsCard";
import { TwoFactorCard } from "@/modules/user-management/account/components/security/TwoFactorCard";
import { Card, PageHeader } from "@/shared/ui";

export function SecurityPage() {
  return (
    <>
      <PageHeader title="Security" description="Password, two-factor authentication and signed-in devices." />
      <div className="space-y-6">
        <Card title="Password" description="Changing your password signs you out on every device.">
          <ChangePasswordForm />
        </Card>
        <TwoFactorCard />
        <SessionsCard />
      </div>
    </>
  );
}
