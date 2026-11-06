import { useListParams } from "@/core/hooks/useListParams";
import { formatDateTime } from "@/core/lib/format";
import { ProctoringTabs } from "@/modules/proctoring/common/components/ProctoringTabs";
import { useListMediaAccessQuery } from "@/modules/proctoring/cases/api/casesApi";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination, type Column } from "@/shared/ui";
import type { MediaAccess } from "@/modules/proctoring/cases/types";

const COLUMNS: Column<MediaAccess>[] = [
  { key: "viewer", header: "Viewer", render: (item) => <UserNameCell userId={item.viewer_user_id} /> },
  { key: "session", header: "Session", render: (item) => `#${item.session_id}` },
  { key: "snapshot", header: "Snapshot", hideOnMobile: true, render: (item) => `#${item.snapshot_id}` },
  { key: "reason", header: "Reason", render: (item) => item.reason },
  { key: "at", header: "At", render: (item) => formatDateTime(item.created_at) },
];

export function MediaAuditPage() {
  const { params, update } = useListParams<{ page: number; per_page: number }>({ page: 1, per_page: 50 });
  const { data, isFetching, isError, refetch } = useListMediaAccessQuery(params);

  return (
    <>
      <PageHeader title="Proctoring" description="Every view of a proctoring snapshot, logged before the link is issued." />
      <ProctoringTabs />
      <Card bodyClassName="p-0">
        {isError ? (
          <EmptyState icon="alert" title="Could not load the audit log" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={COLUMNS}
              rows={data?.items ?? []}
              rowKey={(item) => `${item.snapshot_id}-${item.viewer_user_id}-${item.created_at}`}
              loading={isFetching}
              empty={<EmptyState icon="eye" title="No media views yet" description="Every view of a proctoring snapshot is logged here." />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
