import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { Alert, Button, Icon, Modal } from "@/shared/ui";

interface TemporaryPasswordDialogProps {
  open: boolean;
  name: string;
  username?: string;
  email?: string | null;
  password?: string | null;
  delivery?: "email_link" | "initial_password" | "temporary_password";
  emailSent?: boolean | null;
  setupLink?: string | null;
  message?: string | null;
  onClose: () => void;
}

/** Confirmation dialog shown after user creation with credentials, copy tools, and show/hide controls. */
export function TemporaryPasswordDialog({
  open,
  name,
  username,
  email,
  password,
  delivery,
  emailSent,
  setupLink,
  message,
  onClose,
}: TemporaryPasswordDialogProps) {
  const notify = useNotify();
  const [showPassword, setShowPassword] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const copyToClipboard = async (text: string, fieldName: string, successMsg: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(fieldName);
      notify.success(successMsg);
      setTimeout(() => setCopiedField(null), 3000);
    } catch {
      notify.error("Failed to copy to clipboard.");
    }
  };

  const hasPassword = Boolean(password && password.trim());
  const hasSetupLink = Boolean(setupLink && setupLink.trim());

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${name} created successfully`}
      description={
        delivery === "temporary_password"
          ? "A temporary password was generated. Please copy and share these credentials securely with the user."
          : delivery === "initial_password"
          ? "Initial password set. Share these credentials securely."
          : emailSent
          ? "An account setup link has been emailed to the user."
          : "Account created. Review the credentials and setup link below."
      }
      size="md"
      footer={
        <div className="flex w-full items-center justify-between">
          <span className="text-xs text-slate-500">
            {hasPassword ? "Temporary password will not be shown again after closing." : ""}
          </span>
          <Button variant="primary" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        {hasPassword && (
          <Alert tone="warning" title="Save these credentials now">
            The temporary password is only shown once in this response. The user will be prompted to choose a new password upon initial sign-in.
          </Alert>
        )}

        {delivery === "email_link" && emailSent && (
          <Alert tone="success" title="Invitation sent">
            An account setup invitation email was successfully delivered to {email ?? "the user"}.
          </Alert>
        )}

        {delivery === "email_link" && !emailSent && (
          <Alert tone="info" title="Email in console mode">
            {message || "The email service is in development/console mode. You can copy the one-time account setup link below."}
          </Alert>
        )}

        <dl className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-slate-50 text-sm">
          {/* Full Name */}
          <div className="flex items-center justify-between gap-4 px-4 py-3">
            <dt className="text-slate-500">Full name</dt>
            <dd className="font-medium text-slate-900">{name}</dd>
          </div>

          {/* Email */}
          {email && (
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-slate-500">Email address</dt>
              <dd className="flex items-center gap-2">
                <span className="font-mono text-slate-900">{email}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void copyToClipboard(email, "email", "Email copied")}
                >
                  <Icon name={copiedField === "email" ? "check" : "mail"} size={14} className="mr-1 text-slate-500" />
                  {copiedField === "email" ? "Copied" : "Copy"}
                </Button>
              </dd>
            </div>
          )}

          {/* Username */}
          {username && (
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <dt className="text-slate-500">Username</dt>
              <dd className="flex items-center gap-2">
                <span className="font-mono text-slate-900">{username}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void copyToClipboard(username, "username", "Username copied")}
                >
                  <Icon name={copiedField === "username" ? "check" : "user"} size={14} className="mr-1 text-slate-500" />
                  {copiedField === "username" ? "Copied" : "Copy"}
                </Button>
              </dd>
            </div>
          )}

          {/* Password */}
          {hasPassword && (
            <div className="flex items-center justify-between gap-4 px-4 py-3 bg-amber-50/40">
              <dt className="font-medium text-amber-950">Temporary password</dt>
              <dd className="flex items-center gap-2">
                <span className="font-mono text-base font-semibold tracking-wide text-slate-900 select-all">
                  {showPassword ? password : "•".repeat(Math.max(12, password?.length ?? 12))}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowPassword((prev) => !prev)}
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  <Icon name={showPassword ? "eyeOff" : "eye"} size={14} className="mr-1 text-slate-500" />
                  {showPassword ? "Hide" : "Show"}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void copyToClipboard(password!, "password", "Temporary password copied")}
                >
                  <Icon name={copiedField === "password" ? "check" : "download"} size={14} className="mr-1" />
                  {copiedField === "password" ? "Copied!" : "Copy password"}
                </Button>
              </dd>
            </div>
          )}

          {/* Setup Link if email was not sent */}
          {hasSetupLink && (
            <div className="flex flex-col gap-1.5 px-4 py-3 bg-blue-50/40">
              <div className="flex items-center justify-between">
                <dt className="font-medium text-blue-950">Account set-up link</dt>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void copyToClipboard(setupLink!, "link", "Setup link copied")}
                >
                  <Icon name={copiedField === "link" ? "check" : "download"} size={14} className="mr-1" />
                  {copiedField === "link" ? "Copied!" : "Copy setup link"}
                </Button>
              </div>
              <dd className="break-all font-mono text-xs text-slate-700 bg-white/80 p-2 rounded border border-blue-200">
                {setupLink}
              </dd>
            </div>
          )}
        </dl>
      </div>
    </Modal>
  );
}
