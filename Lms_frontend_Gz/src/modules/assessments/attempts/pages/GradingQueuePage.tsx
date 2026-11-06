import { useState } from "react";

import { useListParams } from "@/core/hooks/useListParams";
import { formatDateTime } from "@/core/lib/format";
import { QUESTION_TYPE_LABELS } from "@/modules/assessments/common/labels";
import { useGetGradingQueueQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { GradeDialog } from "@/modules/assessments/attempts/components/GradeDialog";
import type { GradingQueueItem } from "@/modules/assessments/attempts/gradingTypes";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination, type Column } from "@/shared/ui";

export function GradingQueuePage() {
  const { params, update } = useListParams<{ page: number; per_page: number }>({ page: 1, per_page: 20 });
  const apiParams = params;
  const { data, isFetching, isError, refetch } = useGetGradingQueueQuery(apiParams);
  const [grading, setGrading] = useState<GradingQueueItem | null>(null);

  const columns: Column<GradingQueueItem>[] = [
    { key: "student", header: "Student", render: (item) => <UserNameCell userId={item.user_id} /> },
    { key: "type", header: "Type", hideOnMobile: true, render: (item) => QUESTION_TYPE_LABELS[item.question_type] },
    { key: "text", header: "Question", render: (item) => <span className="line-clamp-1">{item.text}</span> },
    { key: "marks", header: "Marks", hideOnMobile: true, render: (item) => item.marks },
    { key: "submitted", header: "Submitted", hideOnMobile: true, render: (item) => (item.submitted_at ? formatDateTime(item.submitted_at) : "—") },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      className: "w-24 text-right",
      render: (item) => (
        <Button size="sm" onClick={() => setGrading(item)}>
          Grade
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Grading queue" description="Subjective and file submission answers waiting for a human grade." />
      <Card bodyClassName="p-0">
        {isError ? (
          <EmptyState icon="alert" title="Could not load the queue" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable columns={columns} rows={data?.items ?? []} rowKey={(item) => `${item.attempt_id}:${item.question_id}`} loading={isFetching} empty={<EmptyState icon="check" title="Nothing to grade" description="Answers that need a person to mark them appear here." />} />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
      {grading && <GradeDialog open={Boolean(grading)} onClose={() => setGrading(null)} item={grading} />}
    </>
  );
}
