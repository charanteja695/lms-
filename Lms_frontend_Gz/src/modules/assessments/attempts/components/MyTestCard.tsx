import { plural } from "@/core/lib/plural";
import { formatDateTime } from "@/core/lib/format";
import { useStartTest } from "@/modules/assessments/attempts/hooks/useStartTest";
import type { MyTest } from "@/modules/assessments/attempts/types";
import { PROCTORING_LEVEL_LABELS, TEST_KIND_LABELS } from "@/modules/assessments/common/labels";
import { Badge, Button, Icon } from "@/shared/ui";

export function MyTestCard({ test }: { test: MyTest }) {
  const { start: startTest, starting: isLoading } = useStartTest();
  const start = () => startTest(test.test_id);

  return (
    <div className="overflow-hidden rounded-xl border border-[#E5E7EB] bg-white shadow-xs transition-all duration-200 hover:border-[#635BFF]/30 hover:shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="flex items-start gap-4 min-w-0 flex-1">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#F5F4FF] text-[#635BFF]">
            <Icon name="clipboardCheck" size={22} className="text-[#635BFF]" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-md bg-[#F5F4FF] px-2 py-0.5 text-[11px] font-semibold text-[#635BFF] ring-1 ring-[#635BFF]/20">
                {TEST_KIND_LABELS[test.kind]}
              </span>
              <span className="text-[12px] text-[#64748B]">
                {plural(test.question_count, "question")} · {plural(test.total_marks, "mark")}
              </span>
              {test.best_percent != null && (
                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-[#16A37B] ring-1 ring-[#16A37B]/20">
                  <Icon name="check" size={12} /> Best: {test.best_percent.toFixed(0)}%
                </span>
              )}
            </div>

            <h3 className="mt-1.5 text-[16px] font-semibold text-[#111827] truncate">
              {test.title}
            </h3>

            {test.description && (
              <p className="mt-1 text-[12px] text-[#64748B] line-clamp-2">
                {test.description}
              </p>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-3 text-[12px] text-[#64748B]">
              <span className="font-medium text-[#111827]">
                Attempts: {test.attempts_used}
                {test.attempts_left != null && ` of ${test.attempts_used + test.attempts_left}`}
              </span>
              <span className="text-slate-300">·</span>
              <span>
                {PROCTORING_LEVEL_LABELS[test.proctoring_level]} proctoring
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0">
          {test.can_start ? (
            <Button
              size="md"
              loading={isLoading}
              onClick={() => void start()}
              className="h-10 bg-[#635BFF] hover:bg-[#5046E5] text-white rounded-xl text-[14px] font-semibold"
            >
              {test.open_attempt_id ? "Resume Test" : "Start Test"}
            </Button>
          ) : (
            <Badge tone="gray">{test.message ?? "Not available"}</Badge>
          )}
          {!test.can_start && test.next_available_at && (
            <p className="text-[12px] text-[#64748B]">Available {formatDateTime(test.next_available_at)}</p>
          )}
          {!test.can_start && test.opens_at && (
            <p className="text-[12px] text-[#64748B]">Opens {formatDateTime(test.opens_at)}</p>
          )}
        </div>
      </div>
    </div>
  );
}
