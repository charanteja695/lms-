import { VERDICT_LABELS } from "@/modules/code-execution/common/labels";
import type { Verdict } from "@/modules/code-execution/common/types";
import { useGetProblemStatsQuery } from "@/modules/code-execution/problems/api/problemsApi";
import { Card, DescriptionList, StatTile } from "@/shared/ui";

export function ProblemStatsCard({ problemId }: { problemId: string }) {
  const { data: stats } = useGetProblemStatsQuery(problemId);
  if (!stats) return null;

  return (
    <Card title="Statistics">
      <div className="mb-4 grid gap-4 sm:grid-cols-4">
        <StatTile icon="upload" label="Submissions" value={stats.submissions} />
        <StatTile icon="check" label="Accepted" value={stats.accepted} />
        <StatTile icon="graduation" label="Solvers" value={stats.solvers} />
        <StatTile icon="alert" label="Flagged" value={stats.flagged} />
      </div>
      <DescriptionList
        columns={1}
        items={[
          { label: "Acceptance rate", value: `${stats.acceptance_percent}%` },
          ...Object.entries(stats.verdicts).map(([verdict, count]) => ({ label: VERDICT_LABELS[verdict as Verdict] ?? verdict, value: count.toLocaleString() })),
        ]}
      />
    </Card>
  );
}
