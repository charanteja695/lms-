import { useMemo } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDate } from "@/core/lib/format";
import { EnrollmentStatusBadge } from "@/modules/learning/common/components/EnrollmentStatusBadge";
import { useWithdrawEnrollmentMutation } from "@/modules/learning/enrollments/api/enrollmentsApi";
import type { Enrollment } from "@/modules/learning/enrollments/types";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Button, type Column, Icon } from "@/shared/ui";

export function useEnrollmentColumns({ canManage }: { canManage: boolean }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [withdraw] = useWithdrawEnrollmentMutation();
  const columns = useMemo<Column<Enrollment>[]>(
    () => [
      { key: "student", header: "Student", render: (item) => <UserNameCell userId={item.student_user_id} /> },
      { key: "status", header: "Status", render: (item) => <EnrollmentStatusBadge status={item.status} /> },
      { key: "enrolled", header: "Enrolled", hideOnMobile: true, render: (item) => formatDate(item.enrolled_at.slice(0, 10)) },
      {
        key: "actions",
        header: <span className="sr-only">Actions</span>,
        className: "w-12 text-right",
        render: (item) =>
          canManage && item.status === "active" ? (
            <Button
              variant="ghost"
              size="icon"
              aria-label="Withdraw"
              onClick={() =>
                confirm.ask(
                  { title: "Withdraw this student?", description: "Their seat is released immediately.", confirmLabel: "Withdraw" },
                  async () => {
                    try {
                      await withdraw(item.enrollment_id).unwrap();
                      notify.success("Student withdrawn");
                    } catch (error) {
                      notify.apiError(error);
                    }
                  },
                )
              }
            >
              <Icon name="logout" />
            </Button>
          ) : null,
      },
    ],
    [canManage, confirm, notify, withdraw],
  );
  return { columns, confirmDialogProps: confirm.dialogProps };
}
