import { Link, useSearchParams } from "react-router-dom";

import { NewPasswordForm } from "@/modules/user-management/auth/components/NewPasswordForm";
import { AuthCard } from "@/shared/layout/AuthCard";
import { Alert } from "@/shared/ui";

/** Landing page for emailed links: /reset-password?token=… and /set-password?token=… */
export function TokenPasswordPage({ mode }: { mode: "reset" | "setup" }) {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";

  if (token.length < 20) {
    return (
      <AuthCard title="Link not valid" footer={<Link to="/forgot-password" className="font-medium text-brand-600 hover:underline">Request a new link</Link>}>
        <Alert tone="error">This link is incomplete or has expired.</Alert>
      </AuthCard>
    );
  }
  return mode === "setup" ? (
    <NewPasswordForm resetToken={token} title="Set up your account" description="Choose a password to finish setting up your LMS account." />
  ) : (
    <NewPasswordForm resetToken={token} title="Choose a new password" />
  );
}
