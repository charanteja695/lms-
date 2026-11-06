import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { NotificationsTabs } from "@/modules/notifications/common/components/NotificationsTabs";
import { useGetUnreadCountQuery, useListNotificationsQuery, useMarkAllReadMutation } from "@/modules/notifications/inbox/api/inboxApi";
import { NotificationItem } from "@/modules/notifications/inbox/components/NotificationItem";
import { Button, Card, EmptyState, PageHeader, Pagination, Spinner, Tabs } from "@/shared/ui";

type Filter = "all" | "unread";

export function InboxPage() {
  const notify = useNotify();
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const { data, isFetching } = useListNotificationsQuery({ unread: filter === "unread" || undefined, page, per_page: perPage });
  const { data: unread = 0 } = useGetUnreadCountQuery();
  const [markAll, { isLoading }] = useMarkAllReadMutation();
  const items = data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Notifications"
        actions={
          <Button variant="secondary" icon="check" disabled={unread === 0} loading={isLoading} onClick={() => void markAll().unwrap().then((n) => notify.success(`${n} marked as read`), notify.apiError)}>
            Mark all read
          </Button>
        }
      />
      <NotificationsTabs />
      <Card bodyClassName="p-0">
        <div className="border-b border-slate-100 px-4">
          <Tabs<Filter> tabs={[{ value: "all", label: "All" }, { value: "unread", label: `Unread${unread ? ` (${unread})` : ""}` }]} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />
        </div>
        {isFetching && items.length === 0 ? (
          <div className="p-8"><Spinner /></div>
        ) : items.length === 0 ? (
          <EmptyState icon="bell" title={filter === "unread" ? "You're all caught up" : "No notifications yet"} description={filter === "unread" ? "New notifications appear here." : "Updates about your courses, tests and requests appear here."} />
        ) : (
          <ul className="divide-y divide-slate-100">{items.map((n) => <NotificationItem key={n.notification_id} notification={n} />)}</ul>
        )}
        <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={setPage} onPerPageChange={(n) => { setPerPage(n); setPage(1); }} />
      </Card>
    </>
  );
}
