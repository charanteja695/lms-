import { useParams } from "react-router-dom";

import { downloadFile } from "@/core/api/download";
import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDate, formatDateTime } from "@/core/lib/format";
import { DASHBOARD_BY_KEY } from "@/modules/analytics/common/dashboards";
import type { ReportRun } from "@/modules/analytics/common/types";
import { useDeactivateReportMutation, useGetReportQuery, useListReportRunsQuery, useRunReportNowMutation } from "@/modules/analytics/reports/api/reportsApi";
import { FORMAT_LABELS, FREQUENCY_LABELS, RUN_STATUS_LABELS, RUN_STATUS_TONES } from "@/modules/analytics/reports/labels";
import { OrgName } from "@/modules/analytics/common/components/OrgName";
import { Badge, Button, Card, ConfirmDialog, DataTable, DescriptionList, EmptyState, PageHeader, PageLoader, type Column } from "@/shared/ui";

export function ReportDetailPage() {
  const { reportId = "" } = useParams();
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: report, isLoading, isError } = useGetReportQuery(reportId);
  const { data: runs = [], isFetching } = useListReportRunsQuery(reportId, { skip: !report });
  const [runNow, { isLoading: running }] = useRunReportNowMutation();
  const [deactivate] = useDeactivateReportMutation();

  if (isLoading) return <PageLoader />;
  if (isError || !report) return <EmptyState icon="alert" title="Report not found" />;

  const download = (run: ReportRun) =>
    void downloadFile(`/reports/${reportId}/runs/${run.run_id}/download`, {}, `${report.name}.${report.format}`).catch(notify.apiError);

  const columns: Column<ReportRun>[] = [
    { key: "period", header: "Period", render: (r) => (r.period_start ? `${formatDate(r.period_start)} – ${formatDate(r.period_end)}` : "—") },
    { key: "status", header: "Status", render: (r) => <Badge tone={RUN_STATUS_TONES[r.status]}>{RUN_STATUS_LABELS[r.status]}</Badge> },
    { key: "rows", header: "Rows", hideOnMobile: true, render: (r) => r.row_count ?? "—" },
    { key: "when", header: "Generated", hideOnMobile: true, render: (r) => (r.generated_at ? formatDateTime(r.generated_at) : r.error ?? "—") },
    { key: "actions", header: "", render: (r) => r.status === "ready" && <Button size="sm" variant="secondary" icon="download" onClick={() => download(r)}>Download</Button> },
  ];

  return (
    <>
      <PageHeader
        title={report.name}
        description={DASHBOARD_BY_KEY[report.dashboard]?.label}
        backTo="/analytics/reports"
        backLabel="Scheduled reports"
        actions={
          <>
            {report.active && (
              <Button variant="secondary" onClick={() => confirm.ask({ title: "Stop this report?", description: "It won't run again; past runs stay downloadable.", confirmLabel: "Stop", tone: "danger" }, async () => {
                await deactivate(reportId).unwrap().then(() => notify.success("Report stopped"), notify.apiError);
              })}>
                Stop
              </Button>
            )}
            <Button icon="play" loading={running} onClick={() => void runNow(reportId).unwrap().then(() => notify.success("Run started"), notify.apiError)}>Run now</Button>
          </>
        }
      />
      <Card className="mb-4">
        <DescriptionList
          items={[
            { label: "Schedule", value: `${FREQUENCY_LABELS[report.frequency]} · ${FORMAT_LABELS[report.format]}` },
            { label: "Next run", value: report.active ? formatDateTime(report.next_run_at) : "Stopped" },
            ...(report.filters.organization_id ? [{ label: "Institution", value: <OrgName organizationId={report.filters.organization_id} /> }] : []),
            ...(report.filters.employer_id ? [{ label: "Company", value: <OrgName organizationId={report.filters.employer_id} /> }] : []),
          ]}
        />
      </Card>
      <Card title="Runs" bodyClassName="p-0">
        <DataTable columns={columns} rows={runs} rowKey={(r) => r.run_id} loading={isFetching} empty={<EmptyState icon="clock" title="No runs yet" description="Run it to get the first results." />} />
      </Card>
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
