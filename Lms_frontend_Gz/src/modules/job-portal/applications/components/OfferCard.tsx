import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDate, formatDateTime } from "@/core/lib/format";
import { formatCtc } from "@/modules/job-portal/common/format";
import type { Offer } from "@/modules/job-portal/common/types";
import { useRespondToOfferMutation } from "@/modules/job-portal/applications/api/myApplicationsApi";
import { Badge, Button, Card, ConfirmDialog, DescriptionList } from "@/shared/ui";

export function OfferCard({ applicationId, offer }: { applicationId: string; offer: Offer }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [respond, { isLoading }] = useRespondToOfferMutation();
  const pending = offer.status === "extended";

  const answer = (accept: boolean) =>
    confirm.ask(
      { title: accept ? "Accept this offer?" : "Decline this offer?", description: accept ? "The company is told straight away." : "This can't be undone.", confirmLabel: accept ? "Accept" : "Decline", tone: accept ? "primary" : "danger", withReason: true },
      async (note) => {
        try {
          await respond({ id: applicationId, accept, note }).unwrap();
          notify.success(accept ? "Offer accepted — congratulations!" : "Offer declined");
        } catch (error) {
          notify.apiError(error);
        }
      },
    );

  return (
    <Card title="Offer" actions={<Badge tone={pending ? "amber" : offer.status === "accepted" ? "green" : "gray"}>{offer.status}</Badge>}>
      <DescriptionList
        items={[
          { label: "Role", value: offer.role_title },
          { label: "CTC", value: formatCtc(offer.ctc, offer.currency) },
          { label: "Joining", value: offer.joining_date ? formatDate(offer.joining_date) : null },
          { label: pending ? "Answer by" : "Answered", value: pending ? formatDateTime(offer.expires_at) : offer.responded_at ? formatDateTime(offer.responded_at) : null },
          { label: "Note", value: offer.note, span: 2 },
        ]}
      />
      {pending && (
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" disabled={isLoading} onClick={() => answer(false)}>Decline</Button>
          <Button loading={isLoading} onClick={() => answer(true)}>Accept</Button>
        </div>
      )}
      <ConfirmDialog {...confirm.dialogProps} />
    </Card>
  );
}
