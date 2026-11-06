import { useNavigate } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { VerdictBadge } from "@/modules/code-execution/common/components/VerdictBadge";
import { useListSubmissionsQuery } from "@/modules/code-execution/submissions/api/submissionsApi";
import { Card, EmptyState } from "@/shared/ui";

export function SubmissionHistoryCard({ problemId }: { problemId: string }) {
  const navigate = useNavigate();
  const { data, isFetching } = useListSubmissionsQuery({ problem_id: problemId, per_page: 20 });

  const items = data?.items ?? [];

  return (
    <Card title="Your submissions">
      {!isFetching && items.length === 0 ? (
        <EmptyState icon="upload" title="No submissions yet" description="Solve a problem and submit it to see your results here." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {items.map((item) => (
            <li key={item.submission_id}>
              <button
                type="button"
                onClick={() => navigate(`/submissions/${item.submission_id}`)}
                className="flex w-full items-center justify-between gap-3 py-2.5 text-left hover:bg-slate-50"
              >
                <span className="text-sm text-slate-700">
                  {item.language} · {formatDateTime(item.created_at)}
                </span>
                <span className="flex items-center gap-2 text-xs text-slate-500">
                  {item.total_count > 0 && `${item.passed_count}/${item.total_count}`}
                  <VerdictBadge verdict={item.verdict} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
