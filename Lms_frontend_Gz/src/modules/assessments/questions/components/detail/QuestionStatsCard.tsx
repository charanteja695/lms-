import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { useRecomputeStatsMutation } from "@/modules/assessments/questions/api/questionsApi";
import type { QuestionStats } from "@/modules/assessments/questions/types";
import { Button, Card, DescriptionList, EmptyState } from "@/shared/ui";

export function QuestionStatsCard({ questionId, stats }: { questionId: string; stats: QuestionStats | null }) {
  const notify = useNotify();
  const [recompute, { isLoading }] = useRecomputeStatsMutation();

  return (
    <Card
      title="Statistics"
      actions={
        <Button
          variant="secondary"
          size="sm"
          icon="refresh"
          loading={isLoading}
          onClick={async () => {
            try {
              await recompute(questionId).unwrap();
              notify.success("Statistics recomputed");
            } catch (error) {
              notify.apiError(error);
            }
          }}
        >
          Recompute
        </Button>
      }
    >
      {!stats ? (
        <EmptyState icon="alert" title="Not computed yet" description="Statistics appear after enough students have answered this question." />
      ) : (
        <DescriptionList
          items={[
            { label: "Sample size", value: stats.sample_size.toLocaleString() },
            { label: "Difficulty index", value: stats.difficulty_index != null ? stats.difficulty_index.toFixed(2) : null },
            { label: "Discrimination", value: stats.discrimination != null ? stats.discrimination.toFixed(2) : null },
            { label: "Computed", value: formatDateTime(stats.computed_at) },
          ]}
        />
      )}
    </Card>
  );
}
