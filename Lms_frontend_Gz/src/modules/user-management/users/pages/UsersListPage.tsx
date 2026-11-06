import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useCreateUserExportJobMutation, useListAdminsQuery, useListUsersQuery, type UserResource } from "@/modules/user-management/users/api/usersApi";
import { SetPasswordDialog } from "@/modules/user-management/users/components/SetPasswordDialog";
import { UserFilters } from "@/modules/user-management/users/components/list/UserFilters";
import { useUserColumns } from "@/modules/user-management/users/components/list/useUserColumns";
import { useUserActions } from "@/modules/user-management/users/hooks/useUserActions";
import type { UserFilters as Filters } from "@/modules/user-management/users/types";
import { Button, Card, ConfirmDialog, DataTable, EmptyState, ExportMenu, PageHeader, Pagination } from "@/shared/ui";

type ListFilters = Filters & { organization_label?: string };

export function UsersListPage({ resource }: { resource: UserResource }) {
  const isAdmins = resource === "admins";
  const navigate = useNavigate();
  const { permissions } = usePermissions();
  const { params, update, reset } = useListParams<Record<keyof ListFilters, string | boolean | undefined>>({ page: 1, per_page: 20 });
  const { organization_label, ...apiParams } = params as ListFilters & { page: number; per_page: number };

  const usersQuery = useListUsersQuery(apiParams, { skip: isAdmins });
  const adminsQuery = useListAdminsQuery(apiParams, { skip: !isAdmins });
  const { data, isFetching, isError, refetch } = isAdmins ? adminsQuery : usersQuery;
  const [createExportJob] = useCreateUserExportJobMutation();
  const actions = useUserActions(resource);
  const columns = useUserColumns(resource, actions);

  const canCreate = isAdmins ? permissions.admins.create : permissions.users.create_roles.length > 0;
  const { page: _page, per_page: _perPage, search_text, sort_column, sort_order, ...filterValues } = apiParams;
  const activeCount = Object.values({ ...filterValues, search_text }).filter((value) => value !== undefined && value !== "").length;
  const onlyStudents = permissions.users.view_roles.length === 1 && permissions.users.view_roles[0] === "student";
  const title = isAdmins ? "Admins" : onlyStudents ? "Students" : "Users";

  return (
    <>
      <PageHeader
        title={title}
        description={isAdmins ? "Admins own and manage institutions and employers." : "People you can view and manage."}
        actions={
          <>
            {permissions.users.can_export && (
              <ExportMenu
                path={`/${resource}/export`}
                filters={{ ...filterValues, search_text, sort_column, sort_order }}
                fileName={`${resource}.csv`}
                createJob={() => createExportJob({ resource, filters: { ...filterValues, search_text } }).unwrap()}
              />
            )}
            {!isAdmins && permissions.users.can_import && (
              <Button variant="secondary" icon="upload" onClick={() => navigate("/users/import")}>
                Import
              </Button>
            )}
            {canCreate && (
              <Button icon="plus" onClick={() => navigate(`/${resource}/new`)}>
                {isAdmins ? "New admin" : "New user"}
              </Button>
            )}
          </>
        }
      />
      <Card bodyClassName="p-0">
        <UserFilters resource={resource} filters={apiParams} organizationLabel={organization_label} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load the list" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(user) => user.user_id}
              loading={isFetching}
              onRowClick={(user) => navigate(`/${resource}/${user.user_id}`)}
              empty={
                <EmptyState
                  icon="users"
                  title={activeCount ? "No matches" : `No ${title.toLowerCase()} yet`}
                  description={activeCount ? "Try different filters." : undefined}
                  action={activeCount ? <Button variant="secondary" onClick={reset}>Clear filters</Button> : undefined}
                />
              }
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
      <ConfirmDialog {...actions.confirmDialogProps} />
      <SetPasswordDialog {...actions.passwordDialogProps} />
    </>
  );
}
