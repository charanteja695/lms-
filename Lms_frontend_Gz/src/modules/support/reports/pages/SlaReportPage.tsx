import { useState } from "react";

import { useGetSlaReportQuery } from "@/modules/support/reports/api/slaReportApi";
import { SupportManageActions } from "@/modules/support/agent/components/SupportManageActions";
import { Alert, Card, EmptyState, Field, Input, PageHeader, PageLoader, StatTile } from "@/shared/ui";

const percent = (value: number | null) => (value == null ? "—" : `${(value * 100).toFixed(1)}%`);
const minutes = (value: number | null) => (value == null ? "—" : value < 60 ? `${Math.round(value)} min` : `${(value / 60).toFixed(1)} h`);

/** SLA compliance over the agent's own queues, for a chosen period (dates are sent as UTC day bounds). */
export function SlaReportPage() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const { data: report, isFetching, isError } = useGetSlaReportQuery({
    start: start ? `${start}T00:00:00Z` : undefined,
    end: end ? `${end}T23:59:59Z` : undefined,
  });

  return (
    <>
      <PageHeader title="SLA report" description="Your queues; the last 30 days unless you pick dates." actions={<SupportManageActions />} />
      <Card className="mb-4">
        <div className="grid max-w-md gap-4 sm:grid-cols-2">
          <Field label="From">{(props) => <Input {...props} type="date" value={start} onChange={(event) => setStart(event.target.value)} />}</Field>
          <Field label="To">{(props) => <Input {...props} type="date" value={end} onChange={(event) => setEnd(event.target.value)} />}</Field>
        </div>
      </Card>
      {isFetching && !report ? (
        <PageLoader />
      ) : isError || !report ? (
        <EmptyState icon="alert" title="Could not build the report" description="Check the dates: the end must be after the start." />
      ) : (
        <div className="space-y-4">
          {report.truncated && <Alert tone="warning">Too many tickets in this period; the figures cover the first part of it. Pick a shorter range.</Alert>}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile icon="mail" label="Tickets" value={report.tickets} />
            <StatTile icon="check" label="Resolved" value={report.resolved} />
            <StatTile icon="refresh" label="Reopened" value={report.reopened} />
            <StatTile icon="users" label={`Satisfaction (${report.csat_responses})`} value={report.csat_average != null ? `${report.csat_average.toFixed(1)} / 5` : "—"} />
            <StatTile icon="clock" label="First response on time" value={percent(report.first_response_compliance)} />
            <StatTile icon="clock" label="Resolved on time" value={percent(report.resolution_compliance)} />
            <StatTile icon="clock" label="Avg. first response" value={minutes(report.avg_first_response_minutes)} />
            <StatTile icon="clock" label="Avg. resolution" value={minutes(report.avg_resolution_minutes)} />
          </div>
        </div>
      )}
    </>
  );
}
