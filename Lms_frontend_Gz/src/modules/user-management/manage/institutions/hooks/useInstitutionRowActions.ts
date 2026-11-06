import { useCallback } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { useChangeInstitutionStatusMutation, useDeleteInstitutionMutation } from "@/modules/user-management/institutions/api/institutionsApi";
import type { InstitutionListItem } from "@/modules/user-management/institutions/types";
import type { RowActionHandlers } from "@/modules/user-management/manage/common/components/RowActions";

export type InstitutionRowActions = ReturnType<typeof useInstitutionRowActions>;

/** Edit, revoke access (suspend), restore access and delete for one institution, as the server allows. */
export function useInstitutionRowActions(onEdit: (row: InstitutionListItem) => void) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [changeStatus] = useChangeInstitutionStatusMutation();
  const [remove] = useDeleteInstitutionMutation();

  const handlersFor = useCallback(
    (row: InstitutionListItem): RowActionHandlers => {
      const allowed = (action: InstitutionListItem["allowed_actions"][number]) => row.allowed_actions.includes(action);
      const organizationId = row.organization_id;
      return {
        onEdit: allowed("update") ? () => onEdit(row) : undefined,
        onRevoke: allowed("suspend")
          ? () =>
              confirm.ask(
                {
                  title: `Revoke access for ${row.name}?`,
                  description: "Everyone in this institution is signed out and cannot sign in until you restore access. Nothing is deleted.",
                  confirmLabel: "Revoke access",
                },
                async () => {
                  try {
                    await changeStatus({ organizationId, status: "suspended" }).unwrap();
                    notify.success(`Access revoked for ${row.name}`);
                  } catch (error) {
                    notify.apiError(error, "Could not revoke access");
                  }
                },
              )
          : undefined,
        onRestore: allowed("activate")
          ? () =>
              void changeStatus({ organizationId, status: "active" })
                .unwrap()
                .then(() => notify.success(`Access restored for ${row.name}`))
                .catch((error: unknown) => notify.apiError(error, "Could not restore access"))
          : undefined,
        onDelete: allowed("delete")
          ? () =>
              confirm.ask(
                {
                  title: `Delete ${row.name}?`,
                  description: "The institution is removed from the lists. The server only allows this once it has no active people.",
                  confirmLabel: "Delete",
                },
                async () => {
                  try {
                    await remove(organizationId).unwrap();
                    notify.success(`${row.name} deleted`);
                  } catch (error) {
                    notify.apiError(error, "Could not delete");
                  }
                },
              )
          : undefined,
      };
    },
    [changeStatus, confirm, notify, onEdit, remove],
  );

  return { handlersFor, confirmDialogProps: confirm.dialogProps };
}
