import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { DASHBOARD_BY_KEY } from "@/modules/analytics/common/dashboards";
import type { Report } from "@/modules/analytics/common/types";
import { useListReportsQuery } from "@/modules/analytics/reports/api/reportsApi";
import { ReportCreateDialog } from "@/modules/analytics/reports/components/ReportCreateDialog";
import { FORMAT_LABELS, FREQUENCY_LABELS } from "@/modules/analytics/reports/labels";
import { Badge, Button, Card, DataTable, EmptyState, PageHeader, type Column } from "@/shared/ui";

const COLUMNS: Column<Report>[] = [
  { key: "name", header: "Report", render: (r) => <span className="font-medium text-slate-900">{r.name}</span> },
  { key: "dashboard", header: "Dashboard", render: (r) => DASHBOARD_BY_KEY[r.dashboard]?.label ?? r.dashboard },
  { key: "schedule", header: "Schedule", render: (r) => `${FREQUENCY_LABELS[r.frequency]} · ${FORMAT_LABELS[r.format]}` },
  { key: "next", header: "Next run", hideOnMobile: true, render: (r) => (r.active ? formatDateTime(r.next_run_at) : "—") },
  { key: "state", header: "", render: (r) => (r.active ? <Badge tone="green">Active</Badge> : <Badge>Stopped</Badge>) },
];

export function ReportsPage() {
  const navigate = useNavigate();
  const { data = [], isFetching } = useListReportsQuery();
  const { acts, organizationType } = useCan();
  // an institution's own people schedule reports with the Reports page's Export cell; platform staff by their scopes
  const canSchedule = organizationType !== "institution" || acts("reports.export", "analytics.own");
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader title="Scheduled reports" description="Your own saved reports. Each run covers the last 7 days." backTo="/analytics" backLabel="Analytics" actions={canSchedule ? <Button icon="plus" onClick={() => setCreating(true)}>Schedule a report</Button> : undefined} />
      <Card bodyClassName="p-0">
        <DataTable columns={COLUMNS} rows={data} rowKey={(r) => r.report_id} loading={isFetching} onRowClick={(r) => navigate(`/analytics/reports/${r.report_id}`)} empty={<EmptyState icon="clock" title="No scheduled reports" description="Schedule a report to get it as a file regularly." />} />
      </Card>
      {creating && <ReportCreateDialog onClose={() => setCreating(false)} />}
    </>
  );
}
