import { useState } from "react";

import { formatRelative } from "@/core/lib/format";
import { AiTabs } from "@/modules/ai-settings/common/components/AiTabs";
import { formatCount, formatUsd } from "@/modules/ai-settings/common/money";
import type { CallLog } from "@/modules/ai-settings/common/types";
import { useListAiLogsQuery, type LogFilters } from "@/modules/ai-settings/logs/api/logsApi";
import { LogDetailDialog } from "@/modules/ai-settings/logs/components/LogDetailDialog";
import { useAnyInstitutionOptions } from "@/modules/user-management/common/hooks/useDirectoryOptions";
import { Badge, Card, DataTable, EmptyState, EntityPicker, FilterRow, FilterSelect, FilterText, PageHeader, Pagination, type Column } from "@/shared/ui";

const STATUSES = [{ value: "ok", label: "Answered" }, { value: "blocked", label: "Blocked by safety" }, { value: "error", label: "Failed" }];

const COLUMNS: Column<CallLog>[] = [
  { key: "when", header: "When", render: (l) => <span className="whitespace-nowrap">{formatRelative(l.created_at)}</span> },
  { key: "prompt", header: "Prompt", render: (l) => <span className="font-mono text-[13px]">{l.prompt_key ?? l.capability}</span> },
  { key: "service", header: "Service", hideOnMobile: true, render: (l) => l.service },
  { key: "status", header: "Outcome", render: (l) => <Badge tone={l.status === "ok" ? "green" : l.status === "blocked" ? "amber" : "red"}>{STATUSES.find((s) => s.value === l.status)?.label ?? l.status}</Badge> },
  { key: "tokens", header: "Tokens", hideOnMobile: true, render: (l) => formatCount(l.prompt_tokens + l.completion_tokens) },
  { key: "cost", header: "Cost", hideOnMobile: true, render: (l) => formatUsd(l.cost_cents) },
];

/** Every AI call across the platform, newest first, filterable; open one to see what was sent and answered. */
export function LogsPage() {
  const [filters, setFilters] = useState<LogFilters>({});
  const [org, setOrg] = useState<{ id: string; label: string } | null>(null);
  const [paging, setPaging] = useState({ page: 1, per_page: 20 });
  const [open, setOpen] = useState<CallLog | null>(null);
  const { data, isFetching } = useListAiLogsQuery({ ...filters, ...paging });
  const set = (patch: LogFilters) => { setFilters((f) => ({ ...f, ...patch })); setPaging((p) => ({ ...p, page: 1 })); };

  return (
    <>
      <PageHeader title="AI usage & settings" description="Every AI request, with its outcome and cost. Personal data is removed before anything is stored." />
      <AiTabs />
      <Card bodyClassName="p-0">
        <FilterRow activeCount={Object.values(filters).filter(Boolean).length}>
          <div className="w-full sm:w-64">
            <EntityPicker label="Institution" value={org?.id ?? ""} selectedLabel={org?.label} placeholder="Any institution" useOptions={useAnyInstitutionOptions} onChange={(id, label) => { setOrg(id ? { id, label } : null); set({ organization_id: id || undefined }); }} />
          </div>
          <FilterText label="Prompt" value={filters.prompt_key} onChange={(v) => set({ prompt_key: v })} />
          <FilterText label="Service" value={filters.service} onChange={(v) => set({ service: v })} />
          <FilterSelect label="Outcome" value={filters.status} options={STATUSES} onChange={(v) => set({ status: v })} />
        </FilterRow>
        <DataTable columns={COLUMNS} rows={data?.items ?? []} rowKey={(l) => l.call_id} loading={isFetching} onRowClick={setOpen} empty={<EmptyState icon="clock" title="No AI requests" description="Requests appear here as soon as any AI feature is used." />} />
        <Pagination pageContext={data?.pageContext} onPageChange={(page) => setPaging((p) => ({ ...p, page }))} onPerPageChange={(per_page) => setPaging({ page: 1, per_page })} />
      </Card>
      {open && <LogDetailDialog log={open} onClose={() => setOpen(null)} />}
    </>
  );
}
