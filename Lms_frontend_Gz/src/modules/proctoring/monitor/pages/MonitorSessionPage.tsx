import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useParams } from "react-router-dom";

import { formatDateTime, formatRelative } from "@/core/lib/format";
import { useGetMonitorSessionQuery } from "@/modules/proctoring/monitor/api/monitorApi";
import { SessionControls } from "@/modules/proctoring/monitor/components/detail/SessionControls";
import { SessionStatusBadge } from "@/modules/proctoring/common/components/SessionStatusBadge";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Card, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function MonitorSessionPage() {
  const { sessionId = "" } = useParams();
  const { can, acts } = useCan();
  const canControl = can("exams.manage") || acts("proctoring.update", "proctoring.monitor");
  const { data, isLoading, isError } = useGetMonitorSessionQuery(sessionId, { skip: !sessionId });

  if (isLoading) return <PageLoader />;
  if (isError || !data) return <EmptyState icon="alert" title="Session not found" />;

  const { session, directives } = data;

  return (
    <>
      <PageHeader title={session.test_title ? `Live exam · ${session.test_title}` : "Live exam"} description="Live risk, directives and controls." actions={canControl ? <SessionControls sessionId={session.session_id} status={session.status} /> : undefined} />
      <div className="space-y-4">
        <Card title="Overview">
          <DescriptionList
            items={[
              { label: "Student", value: <UserNameCell userId={session.user_id} /> },
              { label: "Test", value: session.test_title ?? "—" },
              { label: "Level", value: session.level },
              { label: "Status", value: <SessionStatusBadge status={session.status} /> },
              { label: "Risk score", value: session.risk_score },
              { label: "Critical", value: session.critical ? <Badge tone="red">Yes</Badge> : "No" },
              { label: "Heartbeat lost", value: session.heartbeat_lost ? <Badge tone="amber">Yes</Badge> : "No" },
              { label: "Last heartbeat", value: formatRelative(session.last_heartbeat_at) },
              { label: "IP address", value: session.ip_address ?? "—" },
              { label: "Consent version", value: session.consent_version ?? "—" },
              { label: "Started", value: formatDateTime(session.started_at) },
            ]}
          />
        </Card>
        <Card title="Risk breakdown">
          {Object.keys(session.risk_breakdown).length === 0 ? (
            <p className="text-sm text-slate-500">No scored events yet.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {Object.entries(session.risk_breakdown).map(([type, points]) => (
                <li key={type} className="flex items-center justify-between">
                  <span className="text-slate-600">{type.replace(/_/g, " ")}</span>
                  <span className="font-medium text-slate-900">{points}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Directives sent">
          {directives.length === 0 ? (
            <p className="text-sm text-slate-500">None yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {directives.map((directive, index) => (
                <li key={index} className="flex items-start justify-between gap-3 border-b border-slate-100 pb-2 last:border-0">
                  <span>
                    <Badge tone="blue">{directive.kind}</Badge> {directive.message}
                  </span>
                  <span className="shrink-0 text-xs text-slate-500">{formatDateTime(directive.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
