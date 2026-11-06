import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import type { UserAction, UserStatus } from "@/modules/user-management/common/types";
import {
  useChangeUserStatusMutation,
  useDeleteUserMutation,
  useResetUserMfaMutation,
  useRevokeUserMutation,
  type UserResource,
} from "@/modules/user-management/users/api/usersApi";
import type { MenuItem } from "@/shared/ui";

export interface ActionTarget {
  user_id: string;
  full_name: string;
  status: UserStatus;
  /** Comes from the server: it decides what this viewer may do with this record. */
  allowed_actions: UserAction[];
}

/**
 * Every management action on a user, with confirmation and feedback. Which items appear is decided by the
 * server (`allowed_actions`), so the rules live in one place. Each API call happens only after confirmation.
 */
export function useUserActions(resource: UserResource) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [changeStatus] = useChangeUserStatusMutation();
  const [revoke] = useRevokeUserMutation();
  const [resetMfa] = useResetUserMfaMutation();
  const [remove] = useDeleteUserMutation();
  const [passwordFor, setPasswordFor] = useState<ActionTarget | null>(null);
  const base = resource === "admins" ? "/admins" : "/users";

  const run = useCallback(
    async (work: () => Promise<{ message: string } | unknown>, success: string) => {
      try {
        const result = (await work()) as { message?: string } | undefined;
        notify.success(success, result && typeof result === "object" && "message" in result ? String(result.message) : undefined);
      } catch (error) {
        notify.apiError(error);
        throw error;
      }
    },
    [notify],
  );

  const itemsFor = useCallback(
    (target: ActionTarget, options: { includeView?: boolean } = {}): MenuItem[] => {
      const allowed = (action: UserAction) => target.allowed_actions.includes(action);
      const params = { resource, userId: target.user_id };

      return [
        { label: "View", icon: "eye", hidden: !options.includeView, onSelect: () => navigate(`${base}/${target.user_id}`) },
        { label: "Edit", icon: "edit", hidden: !allowed("update"), onSelect: () => navigate(`${base}/${target.user_id}/edit`) },
        {
          label: "Suspend",
          icon: "ban",
          hidden: !allowed("suspend"),
          onSelect: () =>
            confirm.ask(
              {
                title: `Suspend ${target.full_name}?`,
                description: "They are signed out immediately and cannot sign in until reactivated.",
                confirmLabel: "Suspend",
                withReason: true,
              },
              (reason) => run(() => changeStatus({ ...params, status: "suspended", reason }).unwrap(), "User suspended"),
            ),
        },
        {
          label: "Activate",
          icon: "play",
          hidden: !allowed("activate"),
          onSelect: () =>
            confirm.ask(
              { title: `Activate ${target.full_name}?`, description: "They will be able to sign in again.", confirmLabel: "Activate", tone: "primary" },
              () => run(() => changeStatus({ ...params, status: "active" }).unwrap(), "User activated"),
            ),
        },
        {
          label: "Set temporary password",
          icon: "key",
          hidden: !allowed("set_password"),
          onSelect: () => setPasswordFor(target),
        },
        {
          label: "Sign out everywhere",
          icon: "logout",
          hidden: !allowed("revoke_sessions"),
          onSelect: () =>
            confirm.ask(
              { title: "Sign out everywhere?", description: `${target.full_name} is signed out of all devices but can sign in again.`, confirmLabel: "Sign out", tone: "primary" },
              () => run(() => revoke(params).unwrap(), "Sessions ended"),
            ),
        },
        {
          label: "Reset two-factor",
          icon: "shield",
          hidden: !allowed("reset_mfa"),
          onSelect: () =>
            confirm.ask(
              { title: "Reset two-factor authentication?", description: "Use this when the person lost their phone. They set it up again at next sign-in.", confirmLabel: "Reset" },
              () => run(() => resetMfa(params).unwrap(), "Two-factor authentication reset"),
            ),
        },
        {
          label: "Delete",
          icon: "trash",
          tone: "danger",
          hidden: !allowed("delete"),
          onSelect: () =>
            confirm.ask(
              {
                title: `Delete ${target.full_name}?`,
                description: "The account is deactivated and hidden. History is kept for auditing.",
                confirmLabel: "Delete",
              },
              async () => {
                await run(() => remove(params).unwrap(), "User deleted");
                navigate(base, { replace: true });
              },
            ),
        },
      ];
    },
    [base, changeStatus, confirm, navigate, remove, resetMfa, resource, revoke, run],
  );

  return {
    itemsFor,
    confirmDialogProps: confirm.dialogProps,
    /** Target of the "Set temporary password" dialog, rendered by the page with <SetPasswordDialog />. */
    passwordDialogProps: { resource, target: passwordFor, onClose: () => setPasswordFor(null) },
  };
}
