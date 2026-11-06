import { useGetAnalyticsQuery } from "@/modules/assessments/tests/api/testsApi";
import { Card, DescriptionList, StatTile } from "@/shared/ui";

export function AnalyticsCard({ testId }: { testId: string }) {
  const { data: analytics } = useGetAnalyticsQuery(testId);
  if (!analytics) return null;

  return (
    <Card title="Analytics">
      <div className="mb-4 grid gap-4 sm:grid-cols-4">
        <StatTile icon="check" label="Graded" value={analytics.graded} />
        <StatTile icon="graduation" label="Pass rate" value={analytics.pass_rate_percent != null ? `${analytics.pass_rate_percent.toFixed(0)}%` : "—"} />
        <StatTile icon="alert" label="Plagiarism flagged" value={analytics.plagiarism_flagged} />
        <StatTile icon="clock" label="Integrity pending" value={analytics.integrity_pending} />
      </div>
      <DescriptionList
        columns={2}
        items={[
          { label: "Average score", value: analytics.average_percent != null ? `${analytics.average_percent.toFixed(1)}%` : null },
          { label: "Average time", value: analytics.average_minutes != null ? `${analytics.average_minutes.toFixed(0)} min` : null },
          ...Object.entries(analytics.attempts).map(([status, count]) => ({ label: status, value: count.toLocaleString() })),
        ]}
      />
    </Card>
  );
}
