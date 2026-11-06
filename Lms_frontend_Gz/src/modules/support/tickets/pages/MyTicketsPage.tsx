import { useSupportRights } from "@/modules/support/common/hooks/useSupportRights";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { env } from "@/core/config/env";
import { useListParams } from "@/core/hooks/useListParams";
import { formatRelative } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { CATEGORY_LABELS, STUDENT_STATUS_LABELS } from "@/modules/support/common/labels";
import { TicketStatusBadge } from "@/modules/support/common/components/TicketBadges";
import type { Ticket, TicketStatus } from "@/modules/support/common/types";
import { useListMyTicketsQuery } from "@/modules/support/tickets/api/myTicketsApi";
import { NewTicketDialog } from "@/modules/support/tickets/components/NewTicketDialog";
import { Button, Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

const COLUMNS: Column<Ticket>[] = [
  { key: "subject", header: "Subject", render: (item) => item.subject },
  { key: "category", header: "Category", hideOnMobile: true, render: (item) => CATEGORY_LABELS[item.category] },
  { key: "status", header: "Status", render: (item) => <TicketStatusBadge status={item.status} forStudent /> },
  { key: "activity", header: "Last activity", hideOnMobile: true, render: (item) => formatRelative(item.last_activity_at ?? item.created_at) },
];

export function MyTicketsPage() {
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const { params, update } = useListParams<{ status: string | undefined }>({ page: 1, per_page: 20 });
  const apiParams = params as { status?: TicketStatus; page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListMyTicketsQuery(apiParams, { pollingInterval: env.liveRefreshMs, skipPollingIfUnfocused: true });

  const { canOpenTicket } = useSupportRights();

  return (
    <>
      <PageHeader
        title="My support tickets"
        description="Ask for help; replies arrive here."
        actions={
          canOpenTicket ? (
            <Button icon="plus" onClick={() => setCreating(true)}>
              New ticket
            </Button>
          ) : undefined
        }
      />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect label="Status" value={apiParams.status} options={toOptions(STUDENT_STATUS_LABELS)} onChange={(value) => update({ status: value })} />
        </FilterRow>
        {isError ? (
          <EmptyState icon="alert" title="Could not load your tickets" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={COLUMNS}
              rows={data?.items ?? []}
              rowKey={(item) => item.ticket_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/support/my-tickets/${item.ticket_id}`)}
              empty={<EmptyState icon="mail" title="No tickets" description="Open one if something isn't working." />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
      {creating && <NewTicketDialog open={creating} onClose={() => setCreating(false)} onCreated={(ticket) => navigate(`/support/my-tickets/${ticket.ticket_id}`)} />}
    </>
  );
}
