import { useState } from "react";

import { useListParams } from "@/core/hooks/useListParams";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { ManageFilters, type ManageFilterValues } from "@/modules/user-management/manage/common/components/ManageFilters";
import { ManagePage } from "@/modules/user-management/manage/common/components/ManagePage";
import { PersonFormModal, type TemporaryPassword } from "@/modules/user-management/manage/people/components/PersonFormModal";
import { usePeopleColumns } from "@/modules/user-management/manage/people/components/usePeopleColumns";
import { PERSON_SCREENS, type PersonKind } from "@/modules/user-management/manage/people/config";
import { usePeopleActions } from "@/modules/user-management/manage/people/hooks/usePeopleActions";
import { useListAdminsQuery, useListUsersQuery } from "@/modules/user-management/users/api/usersApi";
import { TemporaryPasswordDialog } from "@/modules/user-management/users/components/form/TemporaryPasswordDialog";
import type { UserStatus } from "@/modules/user-management/common/types";
import { ConfirmDialog, DataTable, EmptyState } from "@/shared/ui";

/** "new" while adding, a user id while editing, null when the form is closed. */
type FormTarget = "new" | string | null;

/** Admins, Institution heads, Staff or Students: a table, an "Add" button and the same pop-up form for add and edit. */
export function PeoplePage({ kind }: { kind: PersonKind }) {
  const screen = PERSON_SCREENS[kind];
  const isAdmins = screen.resource === "admins";
  const { permissions } = usePermissions();
  const { params, update } = useListParams<Record<keyof ManageFilterValues | "add", string | undefined>>({ page: 1, per_page: 20 });
  // `?add=1` (from the home page buttons) opens the form straight away
  const { organization_label, add, ...apiParams } = params;
  const listParams = { ...apiParams, status: apiParams.status as UserStatus | undefined, ...(isAdmins ? {} : { role: kind }) };

  const usersQuery = useListUsersQuery(listParams, { skip: isAdmins });
  const adminsQuery = useListAdminsQuery(listParams, { skip: !isAdmins });
  const { data, isFetching, isError, refetch } = isAdmins ? adminsQuery : usersQuery;

  const [formTarget, setFormTarget] = useState<FormTarget>(add ? "new" : null);
  const closeForm = () => {
    setFormTarget(null);
    if (add) update({ add: undefined });
  };
  const [temporary, setTemporary] = useState<TemporaryPassword | null>(null);
  const actions = usePeopleActions(screen.resource, (row) => setFormTarget(row.user_id));
  const columns = usePeopleColumns(kind, actions);

  const canAdd = isAdmins ? permissions.admins.create : permissions.users.create_roles.includes(kind);
  const activeFilters = [apiParams.search_text, apiParams.status, apiParams.organization_id].filter(Boolean).length;
  const plural = screen.title.toLowerCase();

  return (
    <>
      <ManagePage
        title={screen.title}
        description={screen.description}
        pageContext={data?.pageContext}
        addLabel={canAdd ? `Add ${screen.one}` : undefined}
        onAdd={() => setFormTarget("new")}
        activeFilters={activeFilters}
        isError={isError}
        onRetry={() => void refetch()}
        isFetching={isFetching}
        onPageChange={(page) => update({ page })}
        onPerPageChange={(perPage) => update({ per_page: perPage })}
        filters={
          <ManageFilters
            values={{ ...apiParams, organization_label }}
            searchPlaceholder={screen.searchPlaceholder}
            showInstitution={!isAdmins && permissions.users.filter_by_institution}
            update={update}
          />
        }
      >
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(row) => row.user_id}
          loading={isFetching}
          empty={
            <EmptyState
              icon="users"
              title={activeFilters ? `No ${plural} match` : `No ${plural} yet`}
              description={activeFilters ? "Try another search or clear the filters." : canAdd ? `Use “Add ${screen.one}” to create the first one.` : undefined}
            />
          }
        />
      </ManagePage>

      {formTarget !== null && (
        <PersonFormModal kind={kind} userId={formTarget === "new" ? null : formTarget} onClose={closeForm} onTemporaryPassword={setTemporary} />
      )}
      <TemporaryPasswordDialog
        open={temporary !== null}
        name={temporary?.name ?? ""}
        username={temporary?.username}
        email={temporary?.email}
        password={temporary?.password}
        delivery={temporary?.delivery}
        emailSent={temporary?.emailSent}
        setupLink={temporary?.setupLink}
        message={temporary?.message}
        onClose={() => setTemporary(null)}
      />
      <ConfirmDialog {...actions.confirmDialogProps} />
    </>
  );
}
