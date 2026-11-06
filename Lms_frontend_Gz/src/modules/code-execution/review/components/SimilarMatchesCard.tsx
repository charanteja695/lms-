import { useNavigate } from "react-router-dom";

import { formatDateTime } from "@/core/lib/format";
import { VerdictBadge } from "@/modules/code-execution/common/components/VerdictBadge";
import { useGetSimilarMatchesQuery } from "@/modules/code-execution/review/api/reviewApi";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Card, EmptyState } from "@/shared/ui";

export function SimilarMatchesCard({ submissionId }: { submissionId: string }) {
  const navigate = useNavigate();
  const { data: matches, isFetching } = useGetSimilarMatchesQuery(submissionId);

  return (
    <Card title="Similar submissions" description="A signal for a human reviewer, never a decision.">
      {!isFetching && (matches?.length ?? 0) === 0 ? (
        <EmptyState icon="graduation" title="No close matches found" description="Nothing in other submissions looks close to this one." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {matches?.map((match) => (
            <li key={match.submission_id}>
              <button
                type="button"
                onClick={() => navigate(`/review/submissions/${match.submission_id}`)}
                className="flex w-full items-center justify-between gap-3 py-2.5 text-left hover:bg-slate-50"
              >
                <span className="text-sm text-slate-700">
                  <UserNameCell userId={match.user_id} /> · {formatDateTime(match.created_at)}
                </span>
                <span className="flex items-center gap-2">
                  <Badge tone="red">{match.similarity_percent}% match</Badge>
                  <VerdictBadge verdict={match.verdict} />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
