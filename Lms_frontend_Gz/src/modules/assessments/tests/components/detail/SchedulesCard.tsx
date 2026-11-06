import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { useCancelScheduleMutation, useListSchedulesQuery } from "@/modules/assessments/tests/api/testsApi";
import { ScheduleFormDialog } from "@/modules/assessments/tests/components/detail/ScheduleFormDialog";
import { Badge, Button, Card, ConfirmDialog, EmptyState, Icon } from "@/shared/ui";

export function SchedulesCard({ testId, canManage }: { testId: string; canManage: boolean }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: schedules, isFetching } = useListSchedulesQuery(testId);
  const [adding, setAdding] = useState(false);
  const [cancelSchedule] = useCancelScheduleMutation();

  return (
    <Card title="Exam windows" description="When this test can be started." actions={canManage && <Button size="sm" icon="plus" onClick={() => setAdding(true)}>Schedule</Button>}>
      {!isFetching && (schedules?.length ?? 0) === 0 ? (
        <EmptyState icon="clock" title="No scheduled windows" description="Add a window to decide when students can take this test." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {schedules?.map((schedule) => (
            <li key={schedule.schedule_id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="text-sm text-slate-700">
                <p>
                  {schedule.title ?? "Exam window"} · {formatDateTime(schedule.starts_at)} – {formatDateTime(schedule.ends_at)}
                </p>
                {schedule.cancelled_at && <Badge tone="red">Cancelled</Badge>}
              </div>
              {canManage && !schedule.cancelled_at && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Cancel schedule"
                  onClick={() =>
                    confirm.ask({ title: "Cancel this window?", description: "Students can no longer start the test in it.", confirmLabel: "Cancel window" }, async () => {
                      try {
                        await cancelSchedule({ testId, scheduleId: schedule.schedule_id }).unwrap();
                        notify.success("Window cancelled");
                      } catch (error) {
                        notify.apiError(error);
                      }
                    })
                  }
                >
                  <Icon name="x" size={14} />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {adding && <ScheduleFormDialog open={adding} onClose={() => setAdding(false)} testId={testId} />}
      <ConfirmDialog {...confirm.dialogProps} />
    </Card>
  );
}
