import { useEffect, useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import { useSetUserPasswordMutation, type UserResource } from "@/modules/user-management/users/api/usersApi";
import { Button, Field, Modal, PasswordInput } from "@/shared/ui";

interface SetPasswordDialogProps {
  resource: UserResource;
  target: { user_id: string; full_name: string } | null;
  onClose: () => void;
}

/** Gives someone a temporary password (e.g. a student without email). They must change it at next sign-in. */
export function SetPasswordDialog({ resource, target, onClose }: SetPasswordDialogProps) {
  const [setPassword, { isLoading }] = useSetUserPasswordMutation();
  const notify = useNotify();
  const [password, setPassword_] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPassword_("");
    setError(null);
  }, [target]);

  const submit = async () => {
    if (!target) return;
    setError(null);
    try {
      await setPassword({ resource, userId: target.user_id, newPassword: password }).unwrap();
      notify.success("Temporary password set", `${target.full_name} must change it at next sign-in.`);
      onClose();
    } catch (caught) {
      const apiError = toApiError(caught);
      const unmatched = applyServerErrors(apiError, () => undefined, () => false);
      setError(unmatched.length ? unmatched.map((detail) => detail.message).join(" ") : apiError.message);
    }
  };

  return (
    <Modal
      open={target !== null}
      onClose={onClose}
      title="Set a temporary password"
      description={target ? `${target.full_name} is signed out everywhere and must choose a new password at next sign-in.` : undefined}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button loading={isLoading} disabled={!password} onClick={() => void submit()}>
            Set password
          </Button>
        </>
      }
    >
      <Field label="Temporary password" error={error ?? undefined} hint="Share it with the person securely." required>
        {(props) => (
          <PasswordInput
            {...props}
            value={password}
            autoComplete="new-password"
            maxLength={128}
            onChange={(event) => setPassword_(event.target.value)}
          />
        )}
      </Field>
    </Modal>
  );
}
