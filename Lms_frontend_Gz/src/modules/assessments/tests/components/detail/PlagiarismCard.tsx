import { useGetPlagiarismQuery } from "@/modules/assessments/tests/api/testsApi";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Card, EmptyState } from "@/shared/ui";

export function PlagiarismCard({ testId }: { testId: string }) {
  const { data: items, isFetching } = useGetPlagiarismQuery(testId);

  return (
    <Card title="Plagiarism signal" description="From code-execution-service's similarity check on coding/SQL answers. A signal for a human, never a decision.">
      {!isFetching && (items?.length ?? 0) === 0 ? (
        <EmptyState icon="graduation" title="No matches found" description="Nothing in other submissions looks close to this one." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {items?.map((item, index) => (
            <li key={index} className="flex items-center justify-between gap-3 py-2.5 text-sm">
              <span className="text-slate-700">
                <UserNameCell userId={item.user_id} /> · {item.language}
              </span>
              {item.similarity_percent != null && <Badge tone="red">{item.similarity_percent}% match</Badge>}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
