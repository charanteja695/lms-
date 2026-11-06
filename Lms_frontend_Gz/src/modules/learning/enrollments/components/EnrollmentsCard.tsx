import { useState } from "react";

import { useListEnrollmentsQuery } from "@/modules/learning/enrollments/api/enrollmentsApi";
import { EnrollDialog } from "@/modules/learning/enrollments/components/EnrollDialog";
import { useEnrollmentColumns } from "@/modules/learning/enrollments/components/list/useEnrollmentColumns";
import { Button, Card, ConfirmDialog, DataTable, EmptyState } from "@/shared/ui";

export function EnrollmentsCard({ batchId, organizationId, canEnroll, canWithdraw }: { batchId: string; organizationId: string; canEnroll: boolean; canWithdraw: boolean }) {
  const [enrolling, setEnrolling] = useState(false);
  const { data, isFetching } = useListEnrollmentsQuery({ batch_id: batchId, per_page: 100 });
  const { columns, confirmDialogProps } = useEnrollmentColumns({ canManage: canWithdraw });

  return (
    <Card title="Students" description="Enrolled students and their status." actions={canEnroll && <Button size="sm" icon="plus" onClick={() => setEnrolling(true)}>Enrol student</Button>}>
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(item) => item.enrollment_id}
        loading={isFetching}
        empty={<EmptyState icon="users" title="No students enrolled yet" description="Enrol students into this batch to get them started." />}
      />
      {enrolling && <EnrollDialog open={enrolling} onClose={() => setEnrolling(false)} batchId={batchId} organizationId={organizationId} />}
      <ConfirmDialog {...confirmDialogProps} />
    </Card>
  );
}
