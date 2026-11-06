import { useState } from "react";

import { formatDateTime } from "@/core/lib/format";
import { useListNotificationTemplatesQuery } from "@/modules/notifications/admin/api/notificationAdminApi";
import { TemplateDialog } from "@/modules/notifications/admin/components/TemplateDialog";
import { NotificationsTabs } from "@/modules/notifications/common/components/NotificationsTabs";
import { CHANNEL_LABELS } from "@/modules/notifications/common/labels";
import type { Template } from "@/modules/notifications/common/types";
import { Badge, Card, DataTable, EmptyState, PageHeader, type Column } from "@/shared/ui";

const COLUMNS: Column<Template>[] = [
  { key: "type", header: "Notification", render: (t) => <span className="font-mono text-xs">{t.type}</span> },
  { key: "channel", header: "Channel", render: (t) => CHANNEL_LABELS[t.channel] },
  { key: "subject", header: "Subject", render: (t) => <span className="line-clamp-1">{t.subject}</span> },
  { key: "state", header: "", render: (t) => (t.is_customised ? <Badge tone="indigo">Customised</Badge> : <Badge>Default</Badge>) },
  { key: "updated", header: "Updated", hideOnMobile: true, render: (t) => (t.updated_at ? formatDateTime(t.updated_at) : "—") },
];

export function TemplatesPage() {
  const { data = [], isFetching } = useListNotificationTemplatesQuery();
  const [editing, setEditing] = useState<Template | null>(null);

  return (
    <>
      <PageHeader title="Notifications" description="The wording of every notification, per channel. Placeholders are filled in when it is sent." />
      <NotificationsTabs />
      <Card bodyClassName="p-0">
        <DataTable columns={COLUMNS} rows={data} rowKey={(t) => `${t.type}/${t.channel}`} loading={isFetching} onRowClick={setEditing} empty={<EmptyState icon="fileText" title="No templates" description="Notification types appear here with their default wording." />} />
      </Card>
      {editing && <TemplateDialog key={`${editing.type}/${editing.channel}`} template={editing} onClose={() => setEditing(null)} />}
    </>
  );
}
