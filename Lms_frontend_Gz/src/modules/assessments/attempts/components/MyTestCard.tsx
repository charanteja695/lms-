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
    <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-card transition-all duration-200 hover:border-brand-300 hover:shadow-lift">
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
        <div className="flex items-start gap-4 min-w-0 flex-1">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-navy-900 to-navy-950 text-white shadow-sm ring-1 ring-navy-800">
            <Icon name="clipboardCheck" size={22} className="text-brand-300" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-md bg-brand-50 px-2 py-0.5 text-xs font-bold text-brand-700 ring-1 ring-brand-200">
                {TEST_KIND_LABELS[test.kind]}
              </span>
              <span className="text-xs text-slate-400">
                {plural(test.question_count, "question")} · {plural(test.total_marks, "mark")}
              </span>
              {test.best_percent != null && (
                <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700 ring-1 ring-emerald-200">
                  <Icon name="check" size={12} /> Best: {test.best_percent.toFixed(0)}%
                </span>
              )}
            </div>

            <h3 className="mt-1.5 text-base sm:text-lg font-bold text-navy-950 truncate">
              {test.title}
            </h3>

            {test.description && (
              <p className="mt-1 text-xs sm:text-sm text-slate-500 line-clamp-2">
                {test.description}
              </p>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
              <span className="font-medium text-slate-600">
                Attempts: {test.attempts_used}
                {test.attempts_left != null && ` of ${test.attempts_used + test.attempts_left}`}
              </span>
              <span className="text-slate-300">·</span>
              <span className="text-slate-500">
                {PROCTORING_LEVEL_LABELS[test.proctoring_level]} proctoring
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2 shrink-0">
          {test.can_start ? (
            <Button
              size="lg"
              loading={isLoading}
              onClick={() => void start()}
              className="bg-brand-600 hover:bg-brand-700 text-white shadow-brand"
            >
              {test.open_attempt_id ? "Resume Test" : "Start Test"}
            </Button>
          ) : (
            <Badge tone="gray">{test.message ?? "Not available"}</Badge>
          )}
          {!test.can_start && test.next_available_at && (
            <p className="text-xs text-slate-500">Available {formatDateTime(test.next_available_at)}</p>
          )}
          {!test.can_start && test.opens_at && (
            <p className="text-xs text-slate-500">Opens {formatDateTime(test.opens_at)}</p>
          )}
        </div>
      </div>
    </div>
  );
}
