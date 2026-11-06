import { useListParams } from "@/core/hooks/useListParams";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { TutorTabs } from "@/modules/ai-tutor/common/components/TutorTabs";
import { ESCALATION_STATUS_LABELS, ESCALATION_STATUS_TONES } from "@/modules/ai-tutor/common/labels";
import type { EscalationStatus } from "@/modules/ai-tutor/common/types";
import { useListEscalationsQuery, useRetryEscalationMutation, type Escalation } from "@/modules/ai-tutor/escalations/api/escalationsApi";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Button, Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, type Column } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(ESCALATION_STATUS_LABELS).map(([value, label]) => ({ value, label }));

/** "Talk to a person" hand-offs from the tutor to support-service; a failed one can be re-queued. */
export function EscalationsPage() {
  const notify = useNotify();
  const { params, update } = useListParams<{ status: string | undefined }>({ page: 1, per_page: 20 });
  const apiParams = params as { status?: EscalationStatus; page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListEscalationsQuery(apiParams);
  const [retry, { isLoading: retrying }] = useRetryEscalationMutation();

  const columns: Column<Escalation>[] = [
    { key: "student", header: "Student", render: (item) => <UserNameCell userId={item.student_user_id} /> },
    { key: "reason", header: "Reason", render: (item) => <span className="line-clamp-2">{item.reason}</span> },
    { key: "category", header: "Category", hideOnMobile: true, render: (item) => item.category },
    { key: "status", header: "Status", render: (item) => <Badge tone={ESCALATION_STATUS_TONES[item.status]}>{ESCALATION_STATUS_LABELS[item.status]}</Badge> },
    { key: "ticket", header: "Ticket", hideOnMobile: true, render: (item) => (item.ticket_id ? `#${item.ticket_id}` : item.last_error ?? "—") },
    { key: "created", header: "Created", hideOnMobile: true, render: (item) => formatDateTime(item.created_at) },
    {
      key: "actions",
      header: "",
      render: (item) =>
        item.status === "failed" && (
          <Button
            variant="secondary"
            size="sm"
            icon="refresh"
            loading={retrying}
            onClick={async () => {
              try {
                await retry(item.escalation_id).unwrap();
                notify.success("Re-queued");
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Retry
          </Button>
        ),
    },
  ];

  return (
    <>
      <PageHeader title="AI tutor" description="Conversations the tutor handed to a person, and whether a support ticket was opened." />
      <TutorTabs />
      <Card bodyClassName="p-0">
        <FilterRow>
          <FilterSelect label="Status" value={apiParams.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
        </FilterRow>
        {isError ? (
          <EmptyState icon="alert" title="Could not load escalations" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable columns={columns} rows={data?.items ?? []} rowKey={(item) => item.escalation_id} loading={isFetching} empty={<EmptyState icon="users" title="No escalations" description="Conversations the tutor hands to a person appear here." />} />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
