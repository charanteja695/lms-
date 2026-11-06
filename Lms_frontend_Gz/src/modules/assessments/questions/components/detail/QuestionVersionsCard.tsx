import { formatDateTime } from "@/core/lib/format";
import { VersionStatusBadge } from "@/modules/assessments/common/components/VersionStatusBadge";
import { useListQuestionVersionsQuery } from "@/modules/assessments/questions/api/questionsApi";
import { Card, EmptyState } from "@/shared/ui";

export function QuestionVersionsCard({ questionId }: { questionId: string }) {
  const { data: versions, isFetching } = useListQuestionVersionsQuery(questionId);
  const sorted = [...(versions ?? [])].sort((a, b) => b.version_no - a.version_no);

  return (
    <Card title="Versions" description="Editing a published question opens a new version; the live one keeps serving until this one is approved.">
      {!isFetching && sorted.length === 0 ? (
        <EmptyState icon="clock" title="No versions yet" description="Each saved change creates a version you can compare here." />
      ) : (
        <ul className="divide-y divide-slate-100">
          {sorted.map((version) => (
            <li key={version.version_no} className="flex items-center justify-between gap-3 py-2.5">
              <span className="text-sm text-slate-700">
                v{version.version_no} · {formatDateTime(version.created_at)}
                {version.review_note && <span className="ml-2 text-slate-500">— {version.review_note}</span>}
              </span>
              <VersionStatusBadge status={version.status} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
