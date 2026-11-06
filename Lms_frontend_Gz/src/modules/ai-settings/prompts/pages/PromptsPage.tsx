import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { AiTabs } from "@/modules/ai-settings/common/components/AiTabs";
import type { Prompt } from "@/modules/ai-settings/common/types";
import { useListPromptsQuery } from "@/modules/ai-settings/prompts/api/promptsApi";
import { NewPromptDialog } from "@/modules/ai-settings/prompts/components/NewPromptDialog";
import { Badge, Button, Card, DataTable, EmptyState, PageHeader, Pagination, type Column } from "@/shared/ui";

const COLUMNS: Column<Prompt>[] = [
  { key: "key", header: "Prompt", render: (p) => (<div><p className="font-mono text-[13px] font-semibold text-navy-950">{p.key}</p><p className="line-clamp-1 text-xs text-slate-500">{p.description || "—"}</p></div>) },
  { key: "service", header: "Used by", hideOnMobile: true, render: (p) => p.owner_service },
  { key: "kind", header: "Kind", render: (p) => <Badge tone={p.capability === "chat" ? "indigo" : "blue"}>{p.capability === "chat" ? "Chat" : "Search"}</Badge> },
  { key: "created", header: "Created", hideOnMobile: true, render: (p) => formatDate(p.created_at) },
];

/** Every instruction the platform's AI follows, by key. Open one to see and change its versions. */
export function PromptsPage() {
  const navigate = useNavigate();
  const [paging, setPaging] = useState({ page: 1, per_page: 20 });
  const [creating, setCreating] = useState(false);
  const { data, isFetching } = useListPromptsQuery(paging);

  return (
    <>
      <PageHeader title="AI usage & settings" description="The instructions behind every AI feature. Each change is a new version that a second person activates." actions={<Button icon="plus" onClick={() => setCreating(true)}>New prompt</Button>} />
      <AiTabs />
      <Card bodyClassName="p-0">
        <DataTable
          columns={COLUMNS}
          rows={data?.items ?? []}
          rowKey={(p) => p.prompt_id}
          loading={isFetching}
          onRowClick={(p) => navigate(`/ai/prompts/${encodeURIComponent(p.key)}`)}
          empty={<EmptyState icon="fileText" title="No prompts yet" description="Services register their prompts here; you can also create one." />}
        />
        <Pagination pageContext={data?.pageContext} onPageChange={(page) => setPaging((p) => ({ ...p, page }))} onPerPageChange={(per_page) => setPaging({ page: 1, per_page })} />
      </Card>
      {creating && <NewPromptDialog open onClose={() => setCreating(false)} />}
    </>
  );
}
