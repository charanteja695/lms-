import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { useListDeliveriesQuery, useRetryDeliveryMutation } from "@/modules/notifications/admin/api/notificationAdminApi";
import { NotificationsTabs } from "@/modules/notifications/common/components/NotificationsTabs";
import { DELIVERY_STATUS_LABELS, DELIVERY_STATUS_TONES } from "@/modules/notifications/common/labels";
import type { Delivery, DeliveryStatus } from "@/modules/notifications/common/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Button, Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

function RetryButton({ delivery }: { delivery: Delivery }) {
  const notify = useNotify();
  const [retry, { isLoading }] = useRetryDeliveryMutation();
  if (delivery.status !== "failed") return null;
  return <Button size="sm" variant="secondary" icon="refresh" loading={isLoading} onClick={() => void retry(delivery.delivery_id).unwrap().then(() => notify.success("Queued for another try"), notify.apiError)}>Retry</Button>;
}

const COLUMNS: Column<Delivery>[] = [
  { key: "to", header: "Recipient", render: (d) => <UserNameCell userId={d.recipient_user_id} /> },
  { key: "status", header: "Status", render: (d) => <Badge tone={DELIVERY_STATUS_TONES[d.status]}>{DELIVERY_STATUS_LABELS[d.status]}</Badge> },
  { key: "attempts", header: "Attempts", render: (d) => d.attempts },
  { key: "error", header: "Last error", hideOnMobile: true, render: (d) => <span className="line-clamp-1 text-xs text-slate-500">{d.last_error ?? "—"}</span> },
  { key: "when", header: "Created", hideOnMobile: true, render: (d) => formatDateTime(d.created_at) },
  { key: "sent", header: "Sent", hideOnMobile: true, render: (d) => (d.sent_at ? formatDateTime(d.sent_at) : "—") },
  { key: "actions", header: "", render: (d) => <RetryButton delivery={d} /> },
];

/** Email deliveries. A failed one has used up its automatic attempts; retrying queues it again. */
export function DeliveriesPage() {
  const [status, setStatus] = useState<DeliveryStatus | undefined>("failed");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const { data, isFetching } = useListDeliveriesQuery({ status, page, per_page: perPage });

  return (
    <>
      <PageHeader title="Notifications" description="Emails that could not be delivered after every automatic try. Retry one to send it again." />
      <NotificationsTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect label="Status" value={status} options={toOptions(DELIVERY_STATUS_LABELS)} onChange={(v) => { setStatus(v as DeliveryStatus | undefined); setPage(1); }} />
        </FilterRow>
        <DataTable columns={COLUMNS} rows={data?.items ?? []} rowKey={(d) => d.delivery_id} loading={isFetching} empty={<EmptyState icon="mail" title="No deliveries" description="Emails that need attention appear here." />} />
        <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={setPage} onPerPageChange={(n) => { setPerPage(n); setPage(1); }} />
      </Card>
    </>
  );
}
