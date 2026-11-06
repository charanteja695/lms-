import { useCallback } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import type { RowActionHandlers } from "@/modules/user-management/manage/common/components/RowActions";
import { useChangeUserStatusMutation, useDeleteUserMutation, type UserResource } from "@/modules/user-management/users/api/usersApi";
import type { UserListItem } from "@/modules/user-management/users/types";

export type PeopleActions = ReturnType<typeof usePeopleActions>;

/**
 * Edit, revoke access (suspend), restore access (activate) and delete for one person. Which ones a row gets is the
 * server's call (`allowed_actions`); revoking and deleting ask first.
 */
export function usePeopleActions(resource: UserResource, onEdit: (row: UserListItem) => void) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [changeStatus] = useChangeUserStatusMutation();
  const [remove] = useDeleteUserMutation();

  const restore = useCallback(
    async (row: UserListItem) => {
      try {
        await changeStatus({ resource, userId: row.user_id, status: "active" }).unwrap();
        notify.success(`Access restored for ${row.full_name}`);
      } catch (error) {
        notify.apiError(error, "Could not restore access");
      }
    },
    [changeStatus, notify, resource],
  );

  const handlersFor = useCallback(
    (row: UserListItem): RowActionHandlers => {
      const allowed = (action: UserListItem["allowed_actions"][number]) => row.allowed_actions.includes(action);
      const params = { resource, userId: row.user_id };
      return {
        onEdit: allowed("update") ? () => onEdit(row) : undefined,
        onRevoke: allowed("suspend")
          ? () =>
              confirm.ask(
                {
                  title: `Revoke access for ${row.full_name}?`,
                  description: "They are signed out everywhere and cannot sign in until you restore access. Nothing is deleted.",
                  confirmLabel: "Revoke access",
                },
                async () => {
                  try {
                    await changeStatus({ ...params, status: "suspended" }).unwrap();
                    notify.success(`Access revoked for ${row.full_name}`);
                  } catch (error) {
                    notify.apiError(error, "Could not revoke access");
                  }
                },
              )
          : undefined,
        onRestore: allowed("activate") ? () => void restore(row) : undefined,
        onDelete: allowed("delete")
          ? () =>
              confirm.ask(
                {
                  title: `Delete ${row.full_name}?`,
                  description: "They are removed from the lists and can no longer sign in. Their history is kept for auditing.",
                  confirmLabel: "Delete",
                },
                async () => {
                  try {
                    await remove(params).unwrap();
                    notify.success(`${row.full_name} deleted`);
                  } catch (error) {
                    notify.apiError(error, "Could not delete");
                  }
                },
              )
          : undefined,
      };
    },
    [changeStatus, confirm, notify, onEdit, remove, resource, restore],
  );

  return { handlersFor, confirmDialogProps: confirm.dialogProps };
}
