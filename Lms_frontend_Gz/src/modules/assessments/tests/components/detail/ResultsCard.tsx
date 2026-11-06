import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { env } from "@/core/config/env";
import { formatDateTime } from "@/core/lib/format";
import { AttemptResultBadge } from "@/modules/assessments/common/components/AttemptResultBadge";
import { AttemptStatusBadge } from "@/modules/assessments/common/components/AttemptStatusBadge";
import { IntegrityStatusBadge } from "@/modules/assessments/common/components/IntegrityStatusBadge";
import { useReleaseResultsMutation } from "@/modules/assessments/tests/api/testsApi";
import { useListAttemptsQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import type { AttemptListItem } from "@/modules/assessments/attempts/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Button, Card, ConfirmDialog, DataTable, EmptyState, Pagination, type Column } from "@/shared/ui";

export function ResultsCard({ testId, canManage }: { testId: string; canManage: boolean }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [page, setPage] = useState(1);
  const { data, isFetching } = useListAttemptsQuery({ test_id: testId, page, per_page: 20 });
  const [releaseResults, { isLoading: releasing }] = useReleaseResultsMutation();

  const columns: Column<AttemptListItem>[] = [
    { key: "student", header: "Student", render: (item) => <UserNameCell userId={item.user_id} /> },
    { key: "status", header: "Status", render: (item) => <AttemptStatusBadge status={item.status} /> },
    { key: "result", header: "Result", render: (item) => <AttemptResultBadge result={item.result} /> },
    { key: "score", header: "Score", hideOnMobile: true, render: (item) => (item.percent != null ? `${item.percent.toFixed(0)}%` : "—") },
    { key: "integrity", header: "Integrity", hideOnMobile: true, render: (item) => <IntegrityStatusBadge status={item.integrity_status} /> },
    { key: "flagged", header: "", render: (item) => (item.plagiarism_flagged ? <Badge tone="red">Flagged</Badge> : null) },
    { key: "submitted", header: "Submitted", hideOnMobile: true, render: (item) => (item.submitted_at ? formatDateTime(item.submitted_at) : "—") },
  ];

  return (
    <Card
      title="Results"
      actions={
        canManage && (
          <>
            <Button
              variant="secondary"
              size="sm"
              icon="download"
              onClick={() => window.open(`${env.apiBaseUrl}/tests/${testId}/results/export`, "_blank")}
            >
              Export CSV
            </Button>
            <Button
              size="sm"
              icon="upload"
              loading={releasing}
              onClick={() =>
                confirm.ask({ title: "Release results?", description: "Students with a manual-release test can then see their score.", confirmLabel: "Release", tone: "primary" }, async () => {
                  try {
                    await releaseResults(testId).unwrap();
                    notify.success("Results released");
                  } catch (error) {
                    notify.apiError(error);
                  }
                })
              }
            >
              Release results
            </Button>
          </>
        )
      }
    >
      <DataTable columns={columns} rows={data?.items ?? []} rowKey={(item) => item.attempt_id} loading={isFetching} empty={<EmptyState icon="users" title="No attempts yet" description="Results appear once students finish this test." />} />
      <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={setPage} onPerPageChange={() => setPage(1)} />
      <ConfirmDialog {...confirm.dialogProps} />
    </Card>
  );
}
