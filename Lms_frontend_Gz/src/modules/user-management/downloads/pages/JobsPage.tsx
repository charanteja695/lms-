import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { downloadFile } from "@/core/api/download";
import { useNotify } from "@/core/hooks/useNotify";
import { formatBytes, formatDateTime, formatRelative } from "@/core/lib/format";
import { useListJobsQuery } from "@/modules/user-management/downloads/api/jobsApi";
import { JOB_STATUS_TONES, JOB_TYPE_LABELS } from "@/modules/user-management/downloads/labels";
import type { Job } from "@/modules/user-management/downloads/types";
import { Badge, Button, Card, type Column, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function JobsPage() {
  const { jobId } = useParams();
  const [searchParams] = useSearchParams();
  const highlight = jobId ?? searchParams.get("highlight");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const notify = useNotify();
  const [downloading, setDownloading] = useState<string | null>(null);

  // Poll only while an export is still being prepared; otherwise no background requests at all.
  const [polling, setPolling] = useState(false);
  const { data, isLoading, isFetching, refetch } = useListJobsQuery({ page, per_page: perPage }, { pollingInterval: polling ? 5000 : 0, skipPollingIfUnfocused: true });
  useEffect(() => {
    setPolling(data?.items.some((job) => job.status === "queued" || job.status === "running") ?? false);
  }, [data]);

  const download = async (job: Job) => {
    setDownloading(job.job_id);
    try {
      await downloadFile(`/jobs/${job.job_id}/download`, {}, job.file_name ?? "export.csv");
    } catch (error) {
      notify.apiError(error, "Download failed");
    } finally {
      setDownloading(null);
    }
  };

  const columns = useMemo<Column<Job>[]>(
    () => [
      {
        key: "type",
        header: "Job",
        render: (job) => (
          <div>
            <p className="font-medium text-slate-900">{JOB_TYPE_LABELS[job.type]}</p>
            <p className="text-xs text-slate-500">Requested {formatRelative(job.created_time)}</p>
            {job.import_summary && (
              <p className="text-xs text-slate-500">
                {job.import_summary.created} created · {job.import_summary.invalid_rows} with problems
                {job.import_summary.dry_run ? " · checked only" : ""}
              </p>
            )}
          </div>
        ),
      },
      {
        key: "status",
        header: "Status",
        render: (job) => (
          <div className="space-y-1">
            <Badge tone={JOB_STATUS_TONES[job.status]}>{job.status[0]?.toUpperCase() + job.status.slice(1)}</Badge>
            {job.error_message && <p className="max-w-xs text-xs text-red-600">{job.error_message}</p>}
          </div>
        ),
      },
      { key: "rows", header: "Rows", hideOnMobile: true, render: (job) => job.row_count?.toLocaleString() ?? "—" },
      { key: "size", header: "Size", hideOnMobile: true, render: (job) => formatBytes(job.file_size_bytes) },
      { key: "expires", header: "Available until", hideOnMobile: true, render: (job) => (job.expires_time ? formatDateTime(job.expires_time) : "—") },
      {
        key: "download",
        header: <span className="sr-only">Download</span>,
        className: "text-right",
        render: (job) =>
          job.status === "completed" ? (
            <Button size="sm" variant="secondary" icon="download" loading={downloading === job.job_id} onClick={() => void download(job)}>
              Download
            </Button>
          ) : null,
      },
    ],
    [downloading],
  );

  return (
    <>
      <PageHeader
        title="Downloads"
        description="Large exports and imports run in the background. Files are kept for 72 hours and only you can download them."
        actions={
          <Button variant="secondary" icon="refresh" loading={isFetching} onClick={() => void refetch()}>
            Refresh
          </Button>
        }
      />
      <Card bodyClassName="p-0">
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(job) => job.job_id}
          loading={isLoading}
          rowClassName={(job) => (job.job_id === highlight ? "bg-brand-50/60" : undefined)}
          empty={<EmptyState icon="download" title="Nothing here yet" description="Background exports and imports appear here with their files." />}
        />
        <Pagination pageContext={data?.pageContext} onPageChange={setPage} onPerPageChange={(next) => { setPerPage(next); setPage(1); }} />
      </Card>
    </>
  );
}
