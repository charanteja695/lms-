import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { formatDateTime } from "@/core/lib/format";
import { useListAuditLogsQuery } from "@/modules/user-management/audit-logs/api/auditLogsApi";
import type { AuditLog, AuditLogFilters } from "@/modules/user-management/audit-logs/types";
import { ROLE_LABELS } from "@/modules/user-management/common/labels";
import { Badge, Card, type Column, DataTable, EmptyState, FilterBar, FilterDate, FilterSelect, PageHeader, Pagination } from "@/shared/ui";

const CATEGORY_OPTIONS = [
  { value: "auth", label: "Sign-in and passwords" },
  { value: "user", label: "Users" },
  { value: "institution", label: "Institutions" },
  { value: "employer", label: "Companies" },
  { value: "job", label: "Exports and imports" },
];

/** "user.password_changed" -> "Password changed": the event's own words, readable; the code stays in the tooltip. */
function actionLabel(action: string): string {
  const words = (action.split(".")[1] ?? action).replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const TARGET_PATH: Record<string, string> = { user: "/users", institution: "/institutions", employer: "/employers" };

/** Who did what and when, scoped by the server to what the viewer may see. */
export function AuditLogPage() {
  const [searchParams] = useSearchParams();
  const { params, update, reset } = useListParams<Record<keyof AuditLogFilters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as AuditLogFilters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListAuditLogsQuery(apiParams);
  const { page: _page, per_page: _perPage, ...filterValues } = apiParams;
  const activeCount = Object.values(filterValues).filter(Boolean).length;
  const aboutUser = searchParams.get("user_id");

  const columns = useMemo<Column<AuditLog>[]>(
    () => [
      { key: "time", header: "When", render: (log) => <span className="whitespace-nowrap">{formatDateTime(log.time)}</span> },
      {
        key: "action",
        header: "Action",
        render: (log) => (
          <p className="font-medium text-slate-900" title={log.action}>{actionLabel(log.action)}</p>
        ),
      },
      {
        key: "actor",
        header: "Who",
        render: (log) =>
          log.actor ? (
            <div className="min-w-0">
              <p className="truncate text-slate-900">{log.actor.full_name}</p>
              <p className="truncate text-xs text-slate-500">{ROLE_LABELS[log.actor.role]}</p>
            </div>
          ) : (
            <span className="text-slate-500">System</span>
          ),
      },
      {
        key: "target",
        header: "What",
        hideOnMobile: true,
        render: (log) => {
          if (!log.target) return "—";
          const path = TARGET_PATH[log.target.type];
          const label = log.target.name ?? log.target.type;
          return path && log.target.id ? (
            <Link className="text-brand-700 hover:underline" to={`${path}/${log.target.id}`}>
              {label}
            </Link>
          ) : (
            <span>{label}</span>
          );
        },
      },
      {
        key: "details",
        header: "Details",
        hideOnMobile: true,
        render: (log) => (
          <div className="flex flex-wrap gap-1">
            {Object.entries(log.details ?? {})
              .slice(0, 3)
              .map(([key, value]) => (
                <Badge key={key}>{`${key}: ${String(value)}`}</Badge>
              ))}
          </div>
        ),
      },
      { key: "ip", header: "IP", hideOnMobile: true, render: (log) => log.ip_address ?? "—" },
    ],
    [],
  );

  return (
    <>
      <PageHeader
        title="Audit log"
        description={aboutUser ? "History of one person." : "Every change and sign-in you are allowed to see, newest first."}
      />
      <Card bodyClassName="p-0">
        <FilterBar
          search={apiParams.search_text ?? ""}
          onSearch={(value) => update({ search_text: value || undefined })}
          searchPlaceholder="Search the action, e.g. suspended"
          activeCount={activeCount}
          onReset={reset}
          primary={
            <FilterSelect label="Category" value={apiParams.category} options={CATEGORY_OPTIONS} onChange={(value) => update({ category: value })} />
          }
          more={
            <>
              <FilterDate label="From" value={apiParams.created_from} onChange={(value) => update({ created_from: value })} />
              <FilterDate label="To" value={apiParams.created_to} onChange={(value) => update({ created_to: value })} />
            </>
          }
        />
        {isError ? (
          <EmptyState icon="alert" title="Could not load the audit log" description="Try again in a moment." action={<button onClick={() => void refetch()}>Retry</button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(log) => log.audit_log_id}
              loading={isFetching}
              empty={<EmptyState icon="search" title="Nothing recorded yet" description="Actions appear here as they happen." />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
