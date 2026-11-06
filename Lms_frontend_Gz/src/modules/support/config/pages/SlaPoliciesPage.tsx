import { useState } from "react";
import { Navigate } from "react-router-dom";

import { PRIORITY_LABELS, QUEUE_LABELS } from "@/modules/support/common/labels";
import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import { PriorityBadge } from "@/modules/support/common/components/TicketBadges";
import { SupportManageActions } from "@/modules/support/agent/components/SupportManageActions";
import { useListSlaPoliciesQuery, type SlaPolicy } from "@/modules/support/config/api/slaPoliciesApi";
import { SlaPolicyDialog } from "@/modules/support/config/components/SlaPolicyDialog";
import { Badge, Card, DataTable, PageHeader, type Column } from "@/shared/ui";

function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 60 * 24) return `${+(minutes / 60).toFixed(1)} h`;
  return `${+(minutes / 60 / 24).toFixed(1)} d`;
}

const COLUMNS: Column<SlaPolicy>[] = [
  { key: "queue", header: "Queue", render: (item) => QUEUE_LABELS[item.queue] },
  { key: "priority", header: "Priority", render: (item) => <PriorityBadge priority={item.priority} /> },
  { key: "first", header: "First response", render: (item) => duration(item.first_response_minutes) },
  { key: "resolution", header: "Resolution", render: (item) => duration(item.resolution_minutes) },
  { key: "default", header: "", render: (item) => (item.is_default ? <Badge tone="gray">Default</Badge> : <Badge tone="blue">Custom</Badge>) },
];

/** Support managers only (the admin API answers 403 to anyone else, so others are sent back to the queue). */
export function SlaPoliciesPage() {
  const { isManager } = useSupportRights();
  const { data: policies = [], isFetching } = useListSlaPoliciesQuery(undefined, { skip: !isManager });
  const [editing, setEditing] = useState<SlaPolicy | null>(null);
  if (!isManager) return <Navigate to="/support/queue" replace />;

  return (
    <>
      <PageHeader title="SLA policies" description={`Response and resolution targets for every queue and priority (${Object.keys(PRIORITY_LABELS).length} priorities per queue).`} actions={<SupportManageActions />} />
      <Card bodyClassName="p-0">
        <DataTable columns={COLUMNS} rows={policies} rowKey={(item) => `${item.queue}:${item.priority}`} loading={isFetching} onRowClick={setEditing} />
      </Card>
      {editing && <SlaPolicyDialog key={`${editing.queue}:${editing.priority}`} policy={editing} onClose={() => setEditing(null)} />}
    </>
  );
}
