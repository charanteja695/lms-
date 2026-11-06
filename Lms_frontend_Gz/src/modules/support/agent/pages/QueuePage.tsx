import { useNavigate } from "react-router-dom";

import { env } from "@/core/config/env";
import { useListParams } from "@/core/hooks/useListParams";
import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import { useListQueueQuery } from "@/modules/support/agent/api/agentTicketsApi";
import { QueueFilters } from "@/modules/support/agent/components/list/QueueFilters";
import { QueueSummaryTiles } from "@/modules/support/agent/components/list/QueueSummaryTiles";
import { useQueueColumns } from "@/modules/support/agent/components/list/useQueueColumns";
import { SupportManageActions } from "@/modules/support/agent/components/SupportManageActions";
import type { QueueFilters as Filters } from "@/modules/support/agent/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function QueuePage() {
  const navigate = useNavigate();
  const { isManager } = useSupportRights();
  const { params, update, reset } = useListParams<Record<keyof Filters, string | boolean | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListQueueQuery(apiParams, { pollingInterval: env.liveRefreshMs, skipPollingIfUnfocused: true });
  const columns = useQueueColumns();
  const activeCount = Object.entries(apiParams).filter(([key, value]) => !["page", "per_page"].includes(key) && value !== undefined && value !== "").length;

  return (
    <>
      <PageHeader title="Support queue" description="Tickets you may handle, most urgent first." actions={<SupportManageActions />} />
      <QueueSummaryTiles />
      <Card bodyClassName="p-0">
        <QueueFilters filters={apiParams} activeCount={activeCount} showQueue={isManager} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load the queue" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.ticket_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/support/queue/${item.ticket_id}`)}
              empty={<EmptyState icon="check" title={activeCount ? "No matches" : "Nothing waiting"} description={activeCount ? "Clear a filter to see more." : "New tickets for your queue appear here."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
