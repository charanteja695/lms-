import { formatDateTime } from "@/core/lib/format";
import { useGetCertificateDetailsQuery, useGetCertificateEventsQuery } from "@/modules/certificates/issued/api/certificatesApi";
import { UserNameCell } from "@/modules/user-management/common/components/UserNameCell";
import { Badge, Card, DescriptionList } from "@/shared/ui";

/** Staff-only: GET /details and /events answer 403 to a student, so this is only mounted for staff and exam managers. */
export function CertificateStaffCards({ certificateId }: { certificateId: string }) {
  const { data: details } = useGetCertificateDetailsQuery(certificateId);
  const { data: events = [] } = useGetCertificateEventsQuery(certificateId);

  return (
    <>
      {details && (
        <Card title="Issue details">
          <DescriptionList
            items={[
              { label: "Attempt", value: `#${details.attempt_id}` },
              { label: "PDF render attempts", value: details.pdf_attempts },
              { label: "Last render error", value: details.last_error, span: 2 },
              { label: "Revoke reason", value: details.revoke_reason, span: 2 },
            ]}
          />
        </Card>
      )}
      <Card title="Audit trail">
        {events.length === 0 ? (
          <p className="text-sm text-slate-500">No events.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {events.map((event, index) => (
              <li key={index} className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2 last:border-0">
                <span className="flex items-center gap-2">
                  <Badge tone={event.event_type === "revoked" || event.event_type === "pdf_failed" ? "red" : "gray"}>{event.event_type.replace(/_/g, " ")}</Badge>
                  {event.actor_user_id && <UserNameCell userId={event.actor_user_id} />}
                </span>
                <span className="shrink-0 text-xs text-slate-500">{formatDateTime(event.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
