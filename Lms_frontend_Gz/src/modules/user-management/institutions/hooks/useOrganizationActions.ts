import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import type { InstitutionStatus, OrganizationAction, OrganizationType, StatusChange } from "@/modules/user-management/common/types";
import {
  useChangeEmployerStatusMutation,
  useDeleteEmployerMutation,
  useRevokeEmployerMutation,
} from "@/modules/user-management/employers/api/employersApi";
import {
  useChangeInstitutionStatusMutation,
  useDeleteInstitutionMutation,
  useRevokeInstitutionMutation,
} from "@/modules/user-management/institutions/api/institutionsApi";
import type { MenuItem } from "@/shared/ui";

export interface OrganizationTarget {
  organization_id: string;
  name: string;
  status: InstitutionStatus;
  allowed_actions: OrganizationAction[];
}

const WORDS = {
  institution: { one: "institution", list: "/institutions" },
  employer: { one: "employer", list: "/employers" },
} as const;

/**
 * Actions on an institution or an employer. The menu is built from the record's `allowed_actions`,
 * so the rules stay in the backend.
 */
export function useOrganizationActions(type: OrganizationType) {
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [changeInstitutionStatus] = useChangeInstitutionStatusMutation();
  const [revokeInstitution] = useRevokeInstitutionMutation();
  const [deleteInstitution] = useDeleteInstitutionMutation();
  const [changeEmployerStatus] = useChangeEmployerStatusMutation();
  const [revokeEmployer] = useRevokeEmployerMutation();
  const [deleteEmployer] = useDeleteEmployerMutation();

  const isEmployer = type === "employer";
  const words = WORDS[type];
  const changeStatus = (args: { organizationId: string; status: StatusChange; reason?: string }) =>
    (isEmployer ? changeEmployerStatus(args) : changeInstitutionStatus(args)).unwrap();
  const revoke = (id: string) => (isEmployer ? revokeEmployer(id) : revokeInstitution(id)).unwrap();
  const remove = (id: string) => (isEmployer ? deleteEmployer(id) : deleteInstitution(id)).unwrap();

  const run = useCallback(
    async (work: () => Promise<unknown>, success: string) => {
      try {
        const result = (await work()) as { message?: string } | undefined;
        notify.success(success, result?.message);
      } catch (error) {
        notify.apiError(error);
        throw error;
      }
    },
    [notify],
  );

  const itemsFor = useCallback(
    (target: OrganizationTarget, options: { includeView?: boolean } = {}): MenuItem[] => {
      const allowed = (action: OrganizationAction) => target.allowed_actions.includes(action);
      const id = target.organization_id;
      return [
        { label: "View", icon: "eye", hidden: !options.includeView, onSelect: () => navigate(`${words.list}/${id}`) },
        { label: "Edit", icon: "edit", hidden: !allowed("update"), onSelect: () => navigate(`${words.list}/${id}/edit`) },
        {
          label: "Suspend",
          icon: "ban",
          hidden: !allowed("suspend"),
          onSelect: () =>
            confirm.ask(
              {
                title: `Suspend ${target.name}?`,
                description: "Every member is signed out and cannot sign in until it is reactivated.",
                confirmLabel: "Suspend",
                withReason: true,
              },
              (reason) => run(() => changeStatus({ organizationId: id, status: "suspended", reason }), `${words.one} suspended`),
            ),
        },
        {
          label: "Activate",
          icon: "play",
          hidden: !allowed("activate"),
          onSelect: () =>
            confirm.ask(
              { title: `Activate ${target.name}?`, description: "Members can sign in again.", confirmLabel: "Activate", tone: "primary" },
              () => run(() => changeStatus({ organizationId: id, status: "active" }), `${words.one} activated`),
            ),
        },
        {
          label: "Sign out all members",
          icon: "logout",
          hidden: !allowed("revoke_sessions"),
          onSelect: () =>
            confirm.ask(
              { title: "Sign out all members?", description: `Everyone in this ${words.one} is signed out. They can sign in again.`, confirmLabel: "Sign out all", tone: "primary" },
              () => run(() => revoke(id), "Members signed out"),
            ),
        },
        {
          label: "Delete",
          icon: "trash",
          tone: "danger",
          hidden: !allowed("delete"),
          onSelect: () =>
            confirm.ask(
              { title: `Delete ${target.name}?`, description: `The ${words.one} is hidden and all its members lose access. History is kept.`, confirmLabel: "Delete" },
              async () => {
                await run(() => remove(id), `${words.one} deleted`);
                navigate(words.list, { replace: true });
              },
            ),
        },
      ];
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [confirm, navigate, run, type],
  );

  return { itemsFor, confirmDialogProps: confirm.dialogProps };
}
