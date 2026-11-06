import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { toOptions } from "@/core/lib/options";
import { StatusBadge } from "@/modules/user-management/common/components/UserBadges";
import { STATUS_LABELS } from "@/modules/user-management/common/labels";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useCreateEmployerExportJobMutation, useListEmployersQuery } from "@/modules/user-management/employers/api/employersApi";
import type { EmployerFilters as Filters, EmployerListItem } from "@/modules/user-management/employers/types";
import { useOrganizationActions } from "@/modules/user-management/institutions/hooks/useOrganizationActions";
import {
  Button,
  Card,
  type Column,
  ConfirmDialog,
  DataTable,
  EmptyState,
  ExportMenu,
  FilterBar,
  FilterSelect,
  FilterText,
  Icon,
  Menu,
  PageHeader,
  Pagination,
} from "@/shared/ui";

export function EmployersListPage() {
  const navigate = useNavigate();
  const { permissions } = usePermissions();
  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListEmployersQuery(apiParams);
  const [createExportJob] = useCreateEmployerExportJobMutation();
  const actions = useOrganizationActions("employer");
  const { page: _page, per_page: _perPage, search_text, sort_column, sort_order, ...filterValues } = apiParams;
  const activeCount = Object.values({ ...filterValues, search_text }).filter(Boolean).length;

  const columns = useMemo<Column<EmployerListItem>[]>(
    () => [
      {
        key: "name",
        header: "Company",
        render: (item) => (
          <div className="min-w-0">
            <Link to={`/employers/${item.organization_id}`} onClick={(event) => event.stopPropagation()} className="block truncate font-medium text-slate-900 hover:text-brand-700">
              {item.name}
            </Link>
            <p className="text-xs text-slate-500">{[item.code, item.industry].filter(Boolean).join(" · ")}</p>
          </div>
        ),
      },
      { key: "location", header: "Location", hideOnMobile: true, render: (item) => `${item.city}, ${item.state}` },
      { key: "status", header: "Status", render: (item) => <StatusBadge status={item.status} /> },
      {
        key: "actions",
        header: <span className="sr-only">Actions</span>,
        className: "w-12 text-right",
        render: (item) => (
          <Menu
            trigger={
              <Button variant="ghost" size="icon" aria-label={`Actions for ${item.name}`}>
                <Icon name="more" />
              </Button>
            }
            items={actions.itemsFor(item, { includeView: true })}
          />
        ),
      },
    ],
    [actions],
  );

  return (
    <>
      <PageHeader
        title="Companies"
        description="Hiring companies. You post their jobs and run their hiring from Jobs."
        actions={
          <>
            <ExportMenu
              path="/employers/export"
              filters={{ ...filterValues, search_text, sort_column, sort_order }}
              fileName="employers.csv"
              createJob={() => createExportJob({ ...filterValues, search_text }).unwrap()}
            />
            {permissions.employers.create && (
              <Button icon="plus" onClick={() => navigate("/employers/new")}>
                New company
              </Button>
            )}
          </>
        }
      />
      <Card bodyClassName="p-0">
        <FilterBar
          search={search_text ?? ""}
          onSearch={(value) => update({ search_text: value || undefined })}
          searchPlaceholder="Search name, code or city"
          activeCount={activeCount}
          onReset={reset}
          primary={
            <FilterSelect
              label="Status"
              value={apiParams.status}
              options={toOptions(STATUS_LABELS, permissions.employers.filter_statuses)}
              onChange={(value) => update({ status: value })}
            />
          }
          more={
            <>
              <FilterText label="Industry" value={apiParams.industry} onChange={(value) => update({ industry: value })} placeholder="Information Technology" />
              <FilterText label="City" value={apiParams.city} onChange={(value) => update({ city: value })} />
              <FilterText label="State" value={apiParams.state} onChange={(value) => update({ state: value })} />
            </>
          }
        />
        {isError ? (
          <EmptyState icon="alert" title="Could not load employers" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.organization_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/employers/${item.organization_id}`)}
              empty={<EmptyState icon="briefcase" title={activeCount ? "No matches" : "No employers yet"} description={activeCount ? "Clear a filter to see more." : "Add a company to let it hire on the platform."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
      <ConfirmDialog {...actions.confirmDialogProps} />
    </>
  );
}
