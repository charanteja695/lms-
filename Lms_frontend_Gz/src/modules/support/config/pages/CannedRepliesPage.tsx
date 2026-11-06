import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import { useListCannedRepliesQuery, useUpdateCannedReplyMutation, type CannedReply } from "@/modules/support/config/api/cannedApi";
import { CannedReplyDialog } from "@/modules/support/config/components/CannedReplyDialog";
import { SupportManageActions } from "@/modules/support/agent/components/SupportManageActions";
import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import { Badge, Button, Card, Checkbox, DataTable, EmptyState, PageHeader, type Column } from "@/shared/ui";

export function CannedRepliesPage() {
  const notify = useNotify();
  const { canWriteCanned, isManager } = useSupportRights();
  // Mirrors ConfigService.authorize_canned: managers edit any reply, institution staff only their institution's (the list only shows their own).
  const canEdit = (item: CannedReply) => isManager || (canWriteCanned && item.scope === "organization");
  const [includeInactive, setIncludeInactive] = useState(false);
  const { data: replies = [], isFetching } = useListCannedRepliesQuery({ include_inactive: includeInactive || undefined });
  const [update] = useUpdateCannedReplyMutation();
  const [editing, setEditing] = useState<CannedReply | null | "new">(null);

  const columns: Column<CannedReply>[] = [
    { key: "title", header: "Title", render: (item) => item.title },
    { key: "scope", header: "Scope", render: (item) => (item.scope === "platform" ? "Platform" : item.organization_id ? <InstitutionNameCell organizationId={item.organization_id} /> : "Institution") },
    { key: "body", header: "Text", hideOnMobile: true, render: (item) => <span className="line-clamp-2 text-slate-600">{item.body}</span> },
    { key: "active", header: "", render: (item) => (item.active ? null : <Badge tone="gray">Inactive</Badge>) },
    {
      key: "toggle",
      header: "",
      render: (item) =>
        canEdit(item) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={async (event) => {
              event.stopPropagation();
              try {
                await update({ cannedId: item.canned_reply_id, active: !item.active }).unwrap();
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            {item.active ? "Deactivate" : "Activate"}
          </Button>
        ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Canned replies"
        description="Saved answers agents can insert into a reply."
        actions={
          <>
            <SupportManageActions />
            {canWriteCanned && (
              <Button icon="plus" onClick={() => setEditing("new")}>
                New reply
              </Button>
            )}
          </>
        }
      />
      <Card bodyClassName="p-0">
        <div className="border-b border-slate-100 p-4">
          <Checkbox label="Show inactive" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />
        </div>
        <DataTable
          columns={columns}
          rows={replies}
          rowKey={(item) => item.canned_reply_id}
          loading={isFetching}
          onRowClick={(item) => canEdit(item) && setEditing(item)}
          empty={<EmptyState icon="fileText" title="No canned replies yet" description="Save replies you send often to answer faster." />}
        />
      </Card>
      {editing && <CannedReplyDialog existing={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}
