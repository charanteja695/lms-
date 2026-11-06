import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { formatDate } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { JobTabs } from "@/modules/job-portal/common/components/JobTabs";
import { DriveStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { DRIVE_STATUS_LABELS } from "@/modules/job-portal/common/labels";
import type { Drive, DriveStatus } from "@/modules/job-portal/common/types";
import { useListDrivesQuery } from "@/modules/job-portal/drives/api/drivesApi";
import { NewDriveDialog } from "@/modules/job-portal/drives/components/NewDriveDialog";
import { Button, Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

export function DrivesPage() {
  const navigate = useNavigate();
  const rights = useJobRights();
  const [creating, setCreating] = useState(false);
  const { params, update } = useListParams<{ status: string | undefined }>({ page: 1, per_page: 20 });
  const apiParams = params as { status?: DriveStatus; page: number; per_page: number };
  const { data, isFetching } = useListDrivesQuery(apiParams);

  const canCreate = rights.isHead || rights.isSuperAdmin || rights.isAdmin;

  const columns: Column<Drive>[] = [
    {
      key: "title",
      header: "Placement Drive",
      className: "min-w-[200px]",
      render: (d) => (
        <div>
          <span className="font-semibold text-slate-900 block truncate">{d.title}</span>
          {d.description && <p className="text-xs text-slate-500 mt-0.5 truncate max-w-[240px]">{d.description}</p>}
        </div>
      ),
    },
    {
      key: "company",
      header: "Hiring Company",
      className: "min-w-[160px]",
      render: (d) => <span className="text-slate-800 font-medium">{d.company_name ?? "—"}</span>,
    },
    {
      key: "institution",
      header: "Institution",
      className: "min-w-[160px]",
      render: (d) => <span className="text-slate-600">{d.institution_name ?? "—"}</span>,
    },
    {
      key: "date",
      header: "Drive Date",
      className: "min-w-[120px]",
      hideOnMobile: true,
      render: (d) => (d.drive_date ? formatDate(d.drive_date) : <span className="text-slate-400">—</span>),
    },
    {
      key: "status",
      header: "Status",
      className: "min-w-[120px]",
      render: (d) => <DriveStatusBadge status={d.status} />,
    },
  ];

  return (
    <>
      <PageHeader
        title="Placement Drives"
        description="Collaborative campus recruitment drives connecting institutions with verified partner companies."
        actions={
          canCreate ? (
            <Button icon="plus" onClick={() => setCreating(true)}>
              Create Placement Drive
            </Button>
          ) : undefined
        }
      />
      <JobTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect
            label="Status"
            value={apiParams.status}
            options={toOptions(DRIVE_STATUS_LABELS)}
            onChange={(value) => update({ status: value })}
          />
        </FilterRow>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(d) => d.drive_id}
          loading={isFetching}
          onRowClick={(d) => navigate(`/jobs/drives/${d.drive_id}`)}
          empty={
            <EmptyState
              icon="users"
              title="No drives yet"
              description="Placement drives connecting institutions and partner companies will appear here."
              action={
                canCreate ? (
                  <Button icon="plus" onClick={() => setCreating(true)}>
                    Create Placement Drive
                  </Button>
                ) : undefined
              }
            />
          }
        />
        <Pagination
          pageContext={data?.pageContext}
          disabled={isFetching}
          onPageChange={(next) => update({ page: next })}
          onPerPageChange={(next) => update({ per_page: next })}
        />
      </Card>
      {creating && (
        <NewDriveDialog
          onClose={() => setCreating(false)}
          onCreated={(id) => navigate(`/jobs/drives/${id}`)}
        />
      )}
    </>
  );
}
